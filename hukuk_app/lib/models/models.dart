/// Citation / source reference from the RAG pipeline.
class Citation {
  final String sourceId;
  final String? sectionHeading;
  final String text;
  final double distance;

  const Citation({
    required this.sourceId,
    this.sectionHeading,
    required this.text,
    required this.distance,
  });

  factory Citation.fromJson(Map<String, dynamic> json) {
    return Citation(
      sourceId: json['source_id'] as String? ?? 'unknown',
      sectionHeading: json['section_heading'] as String?,
      text: json['text'] as String? ?? '',
      distance: (json['distance'] as num?)?.toDouble() ?? 0.0,
    );
  }

  /// Relevance percentage (inverse of cosine distance).
  double get relevancePercent => ((1 - distance) * 100).clamp(0, 100);
}

/// A single chat message (user or assistant).
class ChatMessage {
  final String id;
  final String content;
  final MessageRole role;
  final List<Citation> citations;
  final DateTime timestamp;
  final bool isStreaming;
  final String? model;
  final double? retrievalTimeMs;
  final double? generationTimeMs;

  const ChatMessage({
    required this.id,
    required this.content,
    required this.role,
    this.citations = const [],
    required this.timestamp,
    this.isStreaming = false,
    this.model,
    this.retrievalTimeMs,
    this.generationTimeMs,
  });

  ChatMessage copyWith({
    String? content,
    List<Citation>? citations,
    bool? isStreaming,
    String? model,
    double? retrievalTimeMs,
    double? generationTimeMs,
  }) {
    return ChatMessage(
      id: id,
      content: content ?? this.content,
      role: role,
      citations: citations ?? this.citations,
      timestamp: timestamp,
      isStreaming: isStreaming ?? this.isStreaming,
      model: model ?? this.model,
      retrievalTimeMs: retrievalTimeMs ?? this.retrievalTimeMs,
      generationTimeMs: generationTimeMs ?? this.generationTimeMs,
    );
  }
}

enum MessageRole { user, assistant, system }

/// A chat session (conversation thread).
class ChatSession {
  final String id;
  final String title;
  final DateTime createdAt;
  final DateTime lastMessageAt;
  final List<ChatMessage> messages;

  const ChatSession({
    required this.id,
    required this.title,
    required this.createdAt,
    required this.lastMessageAt,
    this.messages = const [],
  });

  ChatSession copyWith({
    String? title,
    DateTime? lastMessageAt,
    List<ChatMessage>? messages,
  }) {
    return ChatSession(
      id: id,
      title: title ?? this.title,
      createdAt: createdAt,
      lastMessageAt: lastMessageAt ?? this.lastMessageAt,
      messages: messages ?? this.messages,
    );
  }
}

/// Upload result from the API.
class UploadResult {
  final String filename;
  final String sourceId;
  final String documentType;
  final int totalPages;
  final int chunksCreated;
  final String status;
  final List<String> warnings;

  const UploadResult({
    required this.filename,
    required this.sourceId,
    required this.documentType,
    required this.totalPages,
    required this.chunksCreated,
    required this.status,
    this.warnings = const [],
  });

  factory UploadResult.fromJson(Map<String, dynamic> json) {
    return UploadResult(
      filename: json['filename'] as String? ?? '',
      sourceId: json['source_id'] as String? ?? '',
      documentType: json['document_type'] as String? ?? '',
      totalPages: json['total_pages'] as int? ?? 0,
      chunksCreated: json['chunks_created'] as int? ?? 0,
      status: json['status'] as String? ?? 'unknown',
      warnings: (json['warnings'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }

  bool get isSuccess => status == 'success';
}
