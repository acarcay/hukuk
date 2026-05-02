import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../services/api_service.dart';

const _uuid = Uuid();

// ---------------------------------------------------------------------------
// API service singleton
// ---------------------------------------------------------------------------

final apiServiceProvider = Provider<ApiService>((ref) {
  final service = ApiService();
  ref.onDispose(() => service.dispose());
  return service;
});

// ---------------------------------------------------------------------------
// Chat sessions
// ---------------------------------------------------------------------------

final sessionListProvider =
    StateNotifierProvider<SessionListNotifier, List<ChatSession>>((ref) {
  return SessionListNotifier();
});

final activeSessionIdProvider = StateProvider<String?>((ref) => null);

final activeSessionProvider = Provider<ChatSession?>((ref) {
  final id = ref.watch(activeSessionIdProvider);
  if (id == null) return null;
  final sessions = ref.watch(sessionListProvider);
  try {
    return sessions.firstWhere((s) => s.id == id);
  } catch (_) {
    return null;
  }
});

class SessionListNotifier extends StateNotifier<List<ChatSession>> {
  SessionListNotifier() : super([]);

  String createSession({String title = 'Yeni Sohbet'}) {
    final id = _uuid.v4();
    final session = ChatSession(
      id: id,
      title: title,
      createdAt: DateTime.now(),
      lastMessageAt: DateTime.now(),
    );
    state = [session, ...state];
    return id;
  }

  void updateSession(String id, ChatSession updated) {
    state = [
      for (final s in state)
        if (s.id == id) updated else s,
    ];
  }

  void deleteSession(String id) {
    state = state.where((s) => s.id != id).toList();
  }

  void addMessage(String sessionId, ChatMessage message) {
    state = [
      for (final s in state)
        if (s.id == sessionId)
          s.copyWith(
            messages: [...s.messages, message],
            lastMessageAt: DateTime.now(),
            title: s.messages.isEmpty && message.role == MessageRole.user
                ? _truncate(message.content, 40)
                : s.title,
          )
        else
          s,
    ];
  }

  void updateLastMessage(String sessionId, ChatMessage updated) {
    state = [
      for (final s in state)
        if (s.id == sessionId)
          s.copyWith(
            messages: [
              ...s.messages.sublist(0, s.messages.length - 1),
              updated,
            ],
          )
        else
          s,
    ];
  }

  String _truncate(String text, int maxLen) {
    if (text.length <= maxLen) return text;
    return '${text.substring(0, maxLen)}…';
  }
}

// ---------------------------------------------------------------------------
// Chat interaction (streaming)
// ---------------------------------------------------------------------------

final isStreamingProvider = StateProvider<bool>((ref) => false);

final chatControllerProvider = Provider<ChatController>((ref) {
  return ChatController(ref);
});

class ChatController {
  final Ref _ref;

  ChatController(this._ref);

  Future<void> sendMessage(String query) async {
    final api = _ref.read(apiServiceProvider);
    final sessions = _ref.read(sessionListProvider.notifier);

    // Ensure active session
    var sessionId = _ref.read(activeSessionIdProvider);
    if (sessionId == null) {
      sessionId = sessions.createSession();
      _ref.read(activeSessionIdProvider.notifier).state = sessionId;
    }

    // Add user message
    final userMsg = ChatMessage(
      id: _uuid.v4(),
      content: query,
      role: MessageRole.user,
      timestamp: DateTime.now(),
    );
    sessions.addMessage(sessionId, userMsg);

    // Add placeholder assistant message
    final assistantMsg = ChatMessage(
      id: _uuid.v4(),
      content: '',
      role: MessageRole.assistant,
      timestamp: DateTime.now(),
      isStreaming: true,
    );
    sessions.addMessage(sessionId, assistantMsg);

    _ref.read(isStreamingProvider.notifier).state = true;

    try {
      String accumulated = '';
      List<Citation> citations = [];
      String? model;
      double? retrievalMs;
      double? generationMs;

      final allDocs = _ref.read(documentsProvider).value ?? [];
      final deselectedDocs = _ref.read(deselectedDocumentsProvider);
      
      final activeSources = allDocs
          .map((d) => d['source_id'] as String)
          .where((id) => !deselectedDocs.contains(id))
          .toList();

      await for (final event in api.chatStream(
        query: query,
        sourceFilter: activeSources.isEmpty ? null : activeSources,
      )) {
        switch (event.event) {
          case 'context':
            final chunks = event.data['chunks'] as List<dynamic>? ?? [];
            citations = chunks
                .map((c) => Citation.fromJson(c as Map<String, dynamic>))
                .toList();
            break;

          case 'token':
            accumulated += (event.data['token'] as String? ?? '');
            sessions.updateLastMessage(
              sessionId!,
              assistantMsg.copyWith(
                content: accumulated,
                citations: citations,
                isStreaming: true,
              ),
            );
            break;

          case 'done':
            model = event.data['model'] as String?;
            retrievalMs = (event.data['retrieval_time_ms'] as num?)?.toDouble();
            generationMs = (event.data['generation_time_ms'] as num?)?.toDouble();
            break;

          case 'error':
            accumulated += '\n\n⚠️ Error: ${event.data['error']}';
            break;
        }
      }

      // Finalize message
      sessions.updateLastMessage(
        sessionId!,
        assistantMsg.copyWith(
          content: accumulated,
          citations: citations,
          isStreaming: false,
          model: model,
          retrievalTimeMs: retrievalMs,
          generationTimeMs: generationMs,
        ),
      );
    } catch (e) {
      sessions.updateLastMessage(
        sessionId!,
        assistantMsg.copyWith(
          content: 'Bağlantı hatası: $e',
          isStreaming: false,
        ),
      );
    } finally {
      _ref.read(isStreamingProvider.notifier).state = false;
    }
  }
}

// ---------------------------------------------------------------------------
// Upload state
// ---------------------------------------------------------------------------

enum UploadStatus { idle, uploading, success, error }

class UploadState {
  final UploadStatus status;
  final List<UploadResult> results;
  final String? errorMessage;
  final double progress;

  const UploadState({
    this.status = UploadStatus.idle,
    this.results = const [],
    this.errorMessage,
    this.progress = 0.0,
  });
}

final uploadStateProvider =
    StateNotifierProvider<UploadNotifier, UploadState>((ref) {
  return UploadNotifier(ref);
});

class UploadNotifier extends StateNotifier<UploadState> {
  final Ref _ref;

  UploadNotifier(this._ref) : super(const UploadState());

  Future<void> uploadFiles(List<String> paths) async {
    state = const UploadState(status: UploadStatus.uploading, progress: 0.3);

    try {
      final api = _ref.read(apiServiceProvider);
      final results = await api.uploadFiles(paths);
      state = UploadState(
        status: UploadStatus.success,
        results: results,
        progress: 1.0,
      );
    } catch (e) {
      state = UploadState(
        status: UploadStatus.error,
        errorMessage: e.toString(),
      );
    }
  }

  void reset() {
    state = const UploadState();
  }
}

// ---------------------------------------------------------------------------
// Documents state
// ---------------------------------------------------------------------------

final documentsProvider = FutureProvider<List<dynamic>>((ref) async {
  final api = ref.read(apiServiceProvider);
  final response = await api.listDocuments();
  return response['documents'] as List<dynamic>? ?? [];
});

final deselectedDocumentsProvider = StateProvider<List<String>>((ref) => []);

final documentControllerProvider = Provider<DocumentController>((ref) {
  return DocumentController(ref);
});

class DocumentController {
  final Ref _ref;
  DocumentController(this._ref);

  Future<void> deleteDocument(String sourceId) async {
    final api = _ref.read(apiServiceProvider);
    await api.deleteDocument(sourceId);
    
    // Refresh the documents list
    _ref.invalidate(documentsProvider);
    
    // Also remove from deselected list if it was there
    _ref.read(deselectedDocumentsProvider.notifier).update(
      (list) => list.where((id) => id != sourceId).toList(),
    );
  }
}
