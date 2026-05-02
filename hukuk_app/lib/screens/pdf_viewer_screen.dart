import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';

import '../models/models.dart';

class PdfViewerScreen extends StatefulWidget {
  final String sourceId;
  final int pageNumber;
  final String searchText;

  const PdfViewerScreen({
    super.key,
    required this.sourceId,
    required this.pageNumber,
    required this.searchText,
  });

  @override
  State<PdfViewerScreen> createState() => _PdfViewerScreenState();
}

class _PdfViewerScreenState extends State<PdfViewerScreen> {
  final PdfViewerController _pdfViewerController = PdfViewerController();
  PdfTextSearchResult? _searchResult;
  bool _isDocumentLoaded = false;

  @override
  void dispose() {
    _pdfViewerController.dispose();
    super.dispose();
  }

  void _onDocumentLoaded(PdfDocumentLoadedDetails details) async {
    setState(() {
      _isDocumentLoaded = true;
    });
    
    // Jump to the specific page
    _pdfViewerController.jumpToPage(widget.pageNumber);

    // Try to search and highlight the text
    // We only take the first 40 characters to avoid exact matching issues with whitespace/newlines
    final query = widget.searchText.length > 40 
        ? widget.searchText.substring(0, 40).replaceAll('\n', ' ') 
        : widget.searchText.replaceAll('\n', ' ');
        
    _searchResult = await _pdfViewerController.searchText(query);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    // Determine the URL for the PDF
    // Usually it would be baseUrl from config, but we hardcode localhost for simplicity
    final pdfUrl = 'http://localhost:8000/api/v1/documents/files/${widget.sourceId}';

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.sourceId.replaceAll(RegExp(r'^[^_]+_'), '')),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // Allows navigating through search results if multiple were found
              _searchResult?.nextInstance();
            },
          ),
          if (_searchResult != null && _searchResult!.hasResult)
            Padding(
              padding: const EdgeInsets.only(right: 16.0),
              child: Center(
                child: Text(
                  '${_searchResult!.currentInstanceIndex} / ${_searchResult!.totalInstanceCount}',
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ),
            ),
        ],
      ),
      body: Stack(
        children: [
          SfPdfViewer.network(
            pdfUrl,
            controller: _pdfViewerController,
            onDocumentLoaded: _onDocumentLoaded,
            canShowScrollHead: false,
          ),
          if (!_isDocumentLoaded)
            const Center(child: CircularProgressIndicator()),
        ],
      ),
    );
  }
}
