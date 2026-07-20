import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/models.dart';

import 'package:file_picker/file_picker.dart';

/// Service for communicating with the Legal RAG backend API.
class ApiService {
  final String baseUrl;
  final String? apiKey;
  final http.Client _client;

  ApiService({
    String? baseUrl,
    this.apiKey = _defaultApiKey,
    http.Client? client,
  })  : baseUrl = baseUrl ?? _defaultBaseUrl,
        _client = client ?? http.Client();

  /// Base URL — overridable at build/run time with:
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.1.5:8000
  static const String _defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  /// Optional API key sent as the "X-API-Key" header. Provide it with:
  ///   flutter run --dart-define=API_KEY=your-secret
  static const String _defaultApiKey = String.fromEnvironment('API_KEY');

  /// Common headers, including the API key when configured.
  Map<String, String> _headers([Map<String, String>? extra]) {
    final h = <String, String>{...?extra};
    if (apiKey != null && apiKey!.isNotEmpty) {
      h['X-API-Key'] = apiKey!;
    }
    return h;
  }

  // ------------------------------------------------------------------
  // Health check
  // ------------------------------------------------------------------

  Future<Map<String, dynamic>> healthCheck() async {
    final resp =
        await _client.get(Uri.parse('$baseUrl/health'), headers: _headers());
    if (resp.statusCode == 200) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    throw ApiException('Health check failed', resp.statusCode);
  }

  // ------------------------------------------------------------------
  // Upload documents
  // ------------------------------------------------------------------

  Future<List<UploadResult>> uploadPlatformFiles(List<PlatformFile> files) async {
    final uri = Uri.parse('$baseUrl/api/v1/upload');
    final request = http.MultipartRequest('POST', uri);
    request.headers.addAll(_headers());

    for (final file in files) {
      if (file.bytes != null) {
        // For Web
        request.files.add(http.MultipartFile.fromBytes(
          'files',
          file.bytes!,
          filename: file.name,
        ));
      } else if (file.path != null) {
        // For Desktop/Mobile
        request.files.add(await http.MultipartFile.fromPath(
          'files',
          file.path!,
          filename: file.name,
        ));
      }
    }

    final streamedResp = await request.send();
    final resp = await http.Response.fromStream(streamedResp);

    if (resp.statusCode == 200) {
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      final docs = data['documents'] as List<dynamic>? ?? [];
      return docs
          .map((d) => UploadResult.fromJson(d as Map<String, dynamic>))
          .toList();
    }

    throw ApiException(
      _extractError(resp.body),
      resp.statusCode,
    );
  }

  // ------------------------------------------------------------------
  // Chat — non-streaming
  // ------------------------------------------------------------------

  Future<Map<String, dynamic>> chat({
    required String query,
    List<String>? sourceFilter,
    int? topK,
    double? temperature,
    String? language,
  }) async {
    final body = <String, dynamic>{
      'query': query,
      'stream': false,
    };
    if (sourceFilter != null && sourceFilter.isNotEmpty) {
      body['source_filter'] = sourceFilter;
    }
    if (topK != null) body['top_k'] = topK;
    if (temperature != null) body['temperature'] = temperature;
    if (language != null) body['language'] = language;

    final resp = await _client.post(
      Uri.parse('$baseUrl/api/v1/chat'),
      headers: _headers({'Content-Type': 'application/json'}),
      body: jsonEncode(body),
    );

    if (resp.statusCode == 200) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    throw ApiException(_extractError(resp.body), resp.statusCode);
  }

  // ------------------------------------------------------------------
  // Chat — SSE streaming
  // ------------------------------------------------------------------

  /// Returns a stream of SSE events from the /chat endpoint.
  /// Each event is a Map with keys: 'event' (string) and 'data' (parsed JSON).
  Stream<SseEvent> chatStream({
    required String query,
    List<String>? sourceFilter,
    int? topK,
    double? temperature,
    String? language,
  }) async* {
    final body = <String, dynamic>{
      'query': query,
      'stream': true,
    };
    if (sourceFilter != null && sourceFilter.isNotEmpty) {
      body['source_filter'] = sourceFilter;
    }
    if (topK != null) body['top_k'] = topK;
    if (temperature != null) body['temperature'] = temperature;
    if (language != null) body['language'] = language;

    final request = http.Request(
      'POST',
      Uri.parse('$baseUrl/api/v1/chat'),
    );
    request.headers.addAll(_headers({
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    }));
    request.body = jsonEncode(body);

    final streamedResp = await _client.send(request);

    if (streamedResp.statusCode != 200) {
      final resp = await http.Response.fromStream(streamedResp);
      throw ApiException(_extractError(resp.body), resp.statusCode);
    }

    // SSE events are delimited by a blank line ("\n\n"). Network chunks do
    // NOT align with event or even line boundaries, so we accumulate bytes
    // in a persistent buffer and only parse *complete* events (everything up
    // to a "\n\n"), leaving any partial trailing event in the buffer.
    String buffer = '';

    await for (final chunk in streamedResp.stream.transform(utf8.decoder)) {
      buffer += chunk;

      int sepIndex;
      while ((sepIndex = buffer.indexOf('\n\n')) != -1) {
        final rawEvent = buffer.substring(0, sepIndex);
        buffer = buffer.substring(sepIndex + 2);

        final event = _parseSseEvent(rawEvent);
        if (event != null) yield event;
      }
    }

    // Flush any final event that wasn't terminated by a trailing blank line.
    if (buffer.trim().isNotEmpty) {
      final event = _parseSseEvent(buffer);
      if (event != null) yield event;
    }
  }

  /// Parse a single raw SSE event block (its "event:"/"data:" lines) into an
  /// [SseEvent], or null if it is malformed. Supports multi-line data fields.
  SseEvent? _parseSseEvent(String rawEvent) {
    String eventType = '';
    final dataLines = <String>[];

    for (final line in rawEvent.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        // Strip the single optional leading space after the colon.
        var d = line.substring(5);
        if (d.startsWith(' ')) d = d.substring(1);
        dataLines.add(d);
      }
    }

    if (eventType.isEmpty || dataLines.isEmpty) return null;

    try {
      final data = jsonDecode(dataLines.join('\n'));
      return SseEvent(event: eventType, data: data);
    } catch (_) {
      return null; // skip malformed JSON
    }
  }

  // ------------------------------------------------------------------
  // Documents listing
  // ------------------------------------------------------------------

  Future<Map<String, dynamic>> listDocuments() async {
    final resp = await _client.get(
      Uri.parse('$baseUrl/api/v1/documents'),
      headers: _headers(),
    );
    if (resp.statusCode == 200) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    throw ApiException('Failed to list documents', resp.statusCode);
  }

  Future<void> deleteDocument(String sourceId) async {
    final resp = await _client.delete(
      Uri.parse('$baseUrl/api/v1/documents/${Uri.encodeComponent(sourceId)}'),
      headers: _headers(),
    );
    if (resp.statusCode != 200) {
      throw ApiException(_extractError(resp.body), resp.statusCode);
    }
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  String _extractError(String body) {
    try {
      final data = jsonDecode(body) as Map<String, dynamic>;
      return data['detail']?.toString() ?? 'Unknown error';
    } catch (_) {
      return body.length > 200 ? '${body.substring(0, 200)}…' : body;
    }
  }

  void dispose() => _client.close();
}

/// A single Server-Sent Event.
class SseEvent {
  final String event;
  final dynamic data;

  const SseEvent({required this.event, required this.data});
}

/// API error with status code.
class ApiException implements Exception {
  final String message;
  final int statusCode;

  const ApiException(this.message, this.statusCode);

  @override
  String toString() => 'ApiException($statusCode): $message';
}
