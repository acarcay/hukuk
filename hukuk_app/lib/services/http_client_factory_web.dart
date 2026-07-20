import 'package:fetch_client/fetch_client.dart';
import 'package:http/http.dart' as http;

/// Web: use the browser Fetch API instead of XHR.
///
/// The default `http` BrowserClient is XHR-based and buffers the entire
/// response body, so SSE tokens from /chat would only appear after the
/// whole generation finished. FetchClient reads the body via
/// ReadableStream, delivering chunks as they arrive — enabling true
/// token-by-token streaming in the UI.
http.Client createStreamingHttpClient() => FetchClient(mode: RequestMode.cors);
