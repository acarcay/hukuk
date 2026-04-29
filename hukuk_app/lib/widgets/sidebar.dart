import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/models.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';

/// Sidebar with chat history, new chat button, and theme toggle.
class Sidebar extends ConsumerWidget {
  final VoidCallback? onClose;

  const Sidebar({super.key, this.onClose});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessions = ref.watch(sessionListProvider);
    final activeId = ref.watch(activeSessionIdProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      width: 280,
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
        border: Border(
          right: BorderSide(
            color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
          ),
        ),
      ),
      child: Column(
        children: [
          // Header
          Container(
            padding: const EdgeInsets.fromLTRB(20, 16, 12, 16),
            child: Row(
              children: [
                Icon(
                  Icons.balance,
                  color: AppColors.accent,
                  size: 22,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Hukuk AI',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: AppColors.accent,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                if (onClose != null)
                  IconButton(
                    onPressed: onClose,
                    icon: const Icon(Icons.close, size: 20),
                    splashRadius: 18,
                  ),
              ],
            ),
          ),

          // New chat button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  final id = ref.read(sessionListProvider.notifier).createSession();
                  ref.read(activeSessionIdProvider.notifier).state = id;
                },
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Yeni Sohbet'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.accent,
                  side: BorderSide(color: AppColors.accent.withOpacity(0.3)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),

          Divider(height: 1, color: isDark ? AppColors.darkBorder : AppColors.lightBorder),

          // Session list
          Expanded(
            child: sessions.isEmpty
                ? _EmptyState(isDark: isDark)
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: sessions.length,
                    itemBuilder: (context, index) {
                      final session = sessions[index];
                      final isActive = session.id == activeId;

                      return _SessionTile(
                        session: session,
                        isActive: isActive,
                        isDark: isDark,
                        onTap: () {
                          ref.read(activeSessionIdProvider.notifier).state =
                              session.id;
                          onClose?.call();
                        },
                        onDelete: () {
                          ref
                              .read(sessionListProvider.notifier)
                              .deleteSession(session.id);
                          if (isActive) {
                            ref.read(activeSessionIdProvider.notifier).state =
                                null;
                          }
                        },
                      ).animate().fadeIn(
                            delay: Duration(milliseconds: 30 * index),
                            duration: const Duration(milliseconds: 200),
                          );
                    },
                  ),
          ),

          // Bottom controls
          Divider(height: 1, color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                // Theme toggle
                IconButton(
                  onPressed: () {
                    final current = ref.read(themeModeProvider);
                    ref.read(themeModeProvider.notifier).state =
                        current == ThemeMode.dark
                            ? ThemeMode.light
                            : ThemeMode.dark;
                  },
                  icon: Icon(
                    isDark ? Icons.light_mode_outlined : Icons.dark_mode_outlined,
                    size: 20,
                  ),
                  tooltip: isDark ? 'Açık Tema' : 'Koyu Tema',
                ),
                const Spacer(),
                Text(
                  'v1.0.0',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: isDark
                            ? AppColors.textMuted
                            : AppColors.lightTextSecondary,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SessionTile extends StatelessWidget {
  final ChatSession session;
  final bool isActive;
  final bool isDark;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  const _SessionTile({
    required this.session,
    required this.isActive,
    required this.isDark,
    required this.onTap,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: Material(
        color: isActive
            ? AppColors.accent.withOpacity(isDark ? 0.1 : 0.06)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                Icon(
                  Icons.chat_bubble_outline,
                  size: 16,
                  color: isActive
                      ? AppColors.accent
                      : (isDark
                          ? AppColors.textMuted
                          : AppColors.lightTextSecondary),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        session.title,
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontSize: 13,
                                  fontWeight:
                                      isActive ? FontWeight.w600 : FontWeight.w400,
                                  color: isActive
                                      ? (isDark
                                          ? AppColors.textPrimary
                                          : AppColors.lightTextPrimary)
                                      : (isDark
                                          ? AppColors.textSecondary
                                          : AppColors.lightTextSecondary),
                                ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _formatTime(session.lastMessageAt),
                        style: TextStyle(
                          fontSize: 10,
                          color: isDark
                              ? AppColors.textMuted
                              : AppColors.lightTextSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: onDelete,
                  icon: const Icon(Icons.close, size: 14),
                  splashRadius: 14,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 24,
                    minHeight: 24,
                  ),
                  color: isDark
                      ? AppColors.textMuted
                      : AppColors.lightTextSecondary,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'Şimdi';
    if (diff.inHours < 1) return '${diff.inMinutes} dk önce';
    if (diff.inDays < 1) return '${diff.inHours} saat önce';
    return '${dt.day}.${dt.month}.${dt.year}';
  }
}

class _EmptyState extends StatelessWidget {
  final bool isDark;

  const _EmptyState({required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.forum_outlined,
            size: 40,
            color: isDark ? AppColors.textMuted : AppColors.lightTextSecondary,
          ),
          const SizedBox(height: 12),
          Text(
            'Henüz sohbet yok',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: isDark
                      ? AppColors.textMuted
                      : AppColors.lightTextSecondary,
                ),
          ),
        ],
      ),
    );
  }
}
