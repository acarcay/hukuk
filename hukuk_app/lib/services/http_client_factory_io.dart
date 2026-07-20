import 'package:http/http.dart' as http;

/// Native platforms (macOS/iOS/Android/Windows/Linux): the default
/// dart:io-based client already supports streamed response bodies.
http.Client createStreamingHttpClient() => http.Client();
