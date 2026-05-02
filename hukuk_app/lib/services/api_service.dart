import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/models.dart';

/// Service for communicating with the Legal RAG backend API.
class ApiService {
  final String baseUrl;
  final http.Client _client;

  ApiService({
    this.baseUrl = 'http://localhost:8000',
    http.Client? client,
  }) : _client = client ?? http.Client();

  // ------------------------------------------------------------------
  // Health check
  // ------------------------------------------------------------------

  Future<Map<String, dynamic>> healthCheck() async {
    final resp = await _client.get(Uri.parse('$baseUrl/health'));
    if (resp.statusCode == 200) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    throw ApiException('Health check failed', resp.statusCode);
  }

  // ------------------------------------------------------------------
  // Upload documents
  // ------------------------------------------------------------------

  Future<List<UploadResult>> uploadFiles(List<String> filePaths) async {
    final uri = Uri.parse('$baseUrl/api/v1/upload');
    final request = http.MultipartRequest('POST', uri);

    for (final path in filePaths) {
      request.files.add(await http.MultipartFile.fromPath('files', path));
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
      headers: {'Content-Type': 'application/json'},
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
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode(body);

    final streamedResp = await _client.send(request);

    if (streamedResp.statusCode != 200) {
      final resp = await http.Response.fromStream(streamedResp);
      throw ApiException(_extractError(resp.body), resp.statusCode);
    }

    String eventType = '';
    String dataBuffer = '';

    await for (final chunk in streamedResp.stream.transform(utf8.decoder)) {
      final lines = chunk.split('\n');

      for (final line in lines) {
        if (line.startsWith('event: ')) {
          eventType = line.substring(7).trim();
        } else if (line.startsWith('data: ')) {
          dataBuffer = line.substring(6);
        } else if (line.isEmpty && eventType.isNotEmpty && dataBuffer.isNotEmpty) {
          try {
            final data = jsonDecode(dataBuffer);
            yield SseEvent(event: eventType, data: data);
          } catch (_) {
            // skip malformed JSON
          }
          eventType = '';
          dataBuffer = '';
        }
      }
    }
  }

  // ------------------------------------------------------------------
  // Documents listing
  // ------------------------------------------------------------------

  Future<Map<String, dynamic>> listDocuments() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/v1/documents'));
    if (resp.statusCode == 200) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    throw ApiException('Failed to list documents', resp.statusCode);
  }

  Future<void> deleteDocument(String sourceId) async {
    final resp = await _client.delete(
      Uri.parse('$baseUrl/api/v1/documents/$sourceId'),
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
