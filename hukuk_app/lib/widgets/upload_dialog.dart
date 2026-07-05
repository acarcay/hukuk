import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';

/// Document upload dialog with drag-and-drop style UI.
class UploadDialog extends ConsumerWidget {
  const UploadDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showDialog(
      context: context,
      builder: (_) => const UploadDialog(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final uploadState = ref.watch(uploadStateProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Dialog(
      backgroundColor: isDark ? AppColors.darkCard : AppColors.lightCard,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: 480,
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            Row(
              children: [
                Icon(Icons.upload_file, color: AppColors.accent, size: 24),
                const SizedBox(width: 10),
                Text(
                  'Belge Yükleme',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const Spacer(),
                IconButton(
                  onPressed: () {
                    ref.read(uploadStateProvider.notifier).reset();
                    Navigator.of(context).pop();
                  },
                  icon: const Icon(Icons.close, size: 20),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Content based on state
            if (uploadState.status == UploadStatus.idle) _buildPickerUI(context, ref, isDark),
            if (uploadState.status == UploadStatus.uploading) _buildProgress(context, isDark),
            if (uploadState.status == UploadStatus.success) _buildSuccess(context, ref, uploadState, isDark),
            if (uploadState.status == UploadStatus.error) _buildError(context, ref, uploadState, isDark),
          ],
        ),
      ),
    );
  }

  Widget _buildPickerUI(BuildContext context, WidgetRef ref, bool isDark) {
    return Column(
      children: [
        // Drop zone
        GestureDetector(
          onTap: () => _pickAndUpload(ref),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 40),
            decoration: BoxDecoration(
              color: AppColors.accent.withOpacity(0.04),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: AppColors.accent.withOpacity(0.2),
                width: 1.5,
              ),
            ),
            child: Column(
              children: [
                Icon(
                  Icons.cloud_upload_outlined,
                  size: 48,
                  color: AppColors.accent.withOpacity(0.5),
                ),
                const SizedBox(height: 12),
                Text(
                  'Dosya seçmek için tıklayın',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 6),
                Text(
                  'PDF, DOCX, RTF · Maks 50MB',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProgress(BuildContext context, bool isDark) {
    return Column(
      children: [
        const SizedBox(height: 20),
        CircularProgressIndicator(color: AppColors.accent, strokeWidth: 3),
        const SizedBox(height: 20),
        Text(
          'Belgeler işleniyor…\nAyrıştırma → Temizleme → Parçalama → Vektörleme',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildSuccess(BuildContext context, WidgetRef ref, UploadState state, bool isDark) {
    return Column(
      children: [
        Icon(Icons.check_circle, color: AppColors.success, size: 48),
        const SizedBox(height: 12),
        Text('Yükleme Başarılı', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 16),
        ...state.results.map((r) => Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isDark ? AppColors.darkSurfaceAlt : AppColors.lightSurfaceAlt,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: r.isSuccess ? AppColors.success.withOpacity(0.3) : AppColors.error.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    r.isSuccess ? Icons.description : Icons.error_outline,
                    size: 18,
                    color: r.isSuccess ? AppColors.success : AppColors.error,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(r.filename, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 13)),
                        Text(
                          '${r.totalPages} sayfa · ${r.chunksCreated} parça',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            )),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: () {
              ref.read(uploadStateProvider.notifier).reset();
              Navigator.of(context).pop();
            },
            child: const Text('Tamam'),
          ),
        ),
      ],
    );
  }

  Widget _buildError(BuildContext context, WidgetRef ref, UploadState state, bool isDark) {
    return Column(
      children: [
        Icon(Icons.error_outline, color: AppColors.error, size: 48),
        const SizedBox(height: 12),
        Text('Yükleme Hatası', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(
          state.errorMessage ?? 'Bilinmeyen hata',
          style: Theme.of(context).textTheme.bodyMedium,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 20),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            OutlinedButton(
              onPressed: () {
                ref.read(uploadStateProvider.notifier).reset();
                Navigator.of(context).pop();
              },
              child: const Text('Kapat'),
            ),
            const SizedBox(width: 12),
            ElevatedButton(
              onPressed: () {
                ref.read(uploadStateProvider.notifier).reset();
              },
              child: const Text('Tekrar Dene'),
            ),
          ],
        ),
      ],
    );
  }

  Future<void> _pickAndUpload(WidgetRef ref) async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['pdf', 'docx', 'rtf'],
      withData: true,
    );

    if (result != null && result.files.isNotEmpty) {
      ref.read(uploadStateProvider.notifier).uploadPlatformFiles(result.files);
    }
  }
}
