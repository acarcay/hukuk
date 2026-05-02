import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';

class DocumentsDialog extends ConsumerWidget {
  const DocumentsDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showDialog(
      context: context,
      builder: (_) => const DocumentsDialog(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docsAsync = ref.watch(documentsProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Dialog(
      backgroundColor: isDark ? AppColors.darkCard : AppColors.lightCard,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        width: 600,
        height: 500,
        padding: const EdgeInsets.all(28),
        child: Column(
          children: [
            // Header
            Row(
              children: [
                Icon(Icons.folder, color: AppColors.accent, size: 24),
                const SizedBox(width: 10),
                Text(
                  'Sistemdeki Belgeler',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const Spacer(),
                IconButton(
                  onPressed: () => ref.refresh(documentsProvider),
                  icon: const Icon(Icons.refresh, size: 20),
                  tooltip: 'Yenile',
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close, size: 20),
                ),
              ],
            ),
            const SizedBox(height: 20),
            
            // Content
            Expanded(
              child: docsAsync.when(
                data: (docs) {
                  if (docs.isEmpty) {
                    return Center(
                      child: Text(
                        'Henüz belge yüklenmemiş.',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                    );
                  }
                  return ListView.builder(
                    itemCount: docs.length,
                    itemBuilder: (context, index) {
                      final doc = docs[index];
                      final sourceId = doc['source_id'] as String;
                      final isSelected = !ref.watch(deselectedDocumentsProvider).contains(sourceId);

                      return GestureDetector(
                        onTap: () {
                          final deselected = ref.read(deselectedDocumentsProvider);
                          if (isSelected) {
                            // Being unchecked -> Add to deselected
                            ref.read(deselectedDocumentsProvider.notifier).state = 
                                [...deselected, sourceId];
                          } else {
                            // Being checked -> Remove from deselected
                            ref.read(deselectedDocumentsProvider.notifier).state = 
                                deselected.where((id) => id != sourceId).toList();
                          }
                        },
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: isSelected 
                                ? AppColors.accent.withOpacity(0.1) 
                                : (isDark ? AppColors.darkSurfaceAlt : AppColors.lightSurfaceAlt),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: isSelected 
                                  ? AppColors.accent 
                                  : (isDark ? AppColors.darkBorder : AppColors.lightBorder),
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                isSelected ? Icons.check_circle : Icons.circle_outlined, 
                                size: 20, 
                                color: isSelected ? AppColors.accent : AppColors.textMuted,
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _cleanFileName(sourceId),
                                      style: Theme.of(context).textTheme.titleMedium,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ],
                                ),
                                const SizedBox(width: 8),
                                IconButton(
                                  icon: Icon(Icons.delete_outline, size: 18, color: AppColors.error),
                                  onPressed: () async {
                                    final confirm = await showDialog<bool>(
                                      context: context,
                                      builder: (ctx) => AlertDialog(
                                        title: const Text('Belgeyi Sil'),
                                        content: Text('${_cleanFileName(sourceId)} belgesini ve tüm verilerini silmek istediğinize emin misiniz?'),
                                        actions: [
                                          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('İptal')),
                                          TextButton(
                                            onPressed: () => Navigator.pop(ctx, true), 
                                            child: Text('SİL', style: TextStyle(color: AppColors.error)),
                                          ),
                                        ],
                                      ),
                                    );
                                    if (confirm == true) {
                                      await ref.read(documentControllerProvider).deleteDocument(sourceId);
                                    }
                                  },
                                ),
                              ],
                            ),
                          ),
                        );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, st) => Center(
                  child: Text(
                    'Belgeler alınamadı:\n$e',
                    style: TextStyle(color: AppColors.error),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _cleanFileName(String name) {
    if (name.contains('_')) {
      final parts = name.split('_');
      if (parts.first.length == 8) {
        return parts.skip(1).join('_');
      }
    }
    return name;
  }
}
