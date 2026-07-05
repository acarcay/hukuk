import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/chat_input.dart';
import '../widgets/message_bubble.dart';
import '../widgets/sidebar.dart';
import '../widgets/upload_dialog.dart';
import '../widgets/documents_dialog.dart';

/// Main chat screen — sidebar + chat window (responsive layout).
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth > 800;

    // Auto-scroll when messages change
    final activeSession = ref.watch(activeSessionProvider);
    if (activeSession != null && activeSession.messages.isNotEmpty) {
      _scrollToBottom();
    }

    return Scaffold(
      drawer: isDesktop
          ? null
          : Drawer(
              width: 280,
              child: Sidebar(
                onClose: () => Navigator.of(context).pop(),
              ),
            ),
      body: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: const Alignment(-0.8, -0.6),
            radius: 1.5,
            colors: [
              AppColors.meshGlow1.withOpacity(0.4),
              AppColors.darkBg,
              AppColors.meshGlow2.withOpacity(0.3),
            ],
            stops: const [0.0, 0.5, 1.0],
          ),
        ),
        child: Row(
        children: [
          // Sidebar (desktop only)
          if (isDesktop) const Sidebar(),

          // Main chat area
          Expanded(
            child: Column(
              children: [
                // App bar
                _ChatAppBar(isDesktop: isDesktop),

                // Messages
                Expanded(
                  child: activeSession == null
                      ? _WelcomeView()
                      : _MessageList(
                          session: activeSession,
                          scrollController: _scrollController,
                        ),
                ),

                // Input
                ChatInput(
                  onUploadTap: () => UploadDialog.show(context),
                ),
              ],
            ),
          ),
        ],
      ),
      ),
    );
  }
}

/// Top bar with session title and actions.
class _ChatAppBar extends ConsumerWidget {
  final bool isDesktop;

  const _ChatAppBar({required this.isDesktop});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(activeSessionProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          height: 60,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: isDark ? AppColors.darkSurface : AppColors.lightSurface.withOpacity(0.8),
            border: Border(
              bottom: BorderSide(
                color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
                width: 1,
              ),
            ),
          ),
      child: Row(
        children: [
          if (!isDesktop)
            IconButton(
              onPressed: () => Scaffold.of(context).openDrawer(),
              icon: const Icon(Icons.menu, size: 22),
            ),
          if (!isDesktop) const SizedBox(width: 4),
          if (!isDesktop)
            Icon(Icons.balance, color: AppColors.accent, size: 20),
          if (!isDesktop) const SizedBox(width: 8),
          Expanded(
            child: Text(
              session?.title ?? 'Hukuk AI',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // View documents button
          IconButton(
            onPressed: () {
              ref.refresh(documentsProvider); // refresh before showing
              DocumentsDialog.show(context);
            },
            icon: const Icon(Icons.folder_outlined, size: 22),
            tooltip: 'Sistemdeki Belgeler',
          ),
          // Status indicator
          _ConnectionStatus(),
        ],
      ),
    )));
  }
}

/// Green/red dot showing API connectivity.
class _ConnectionStatus extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Tooltip(
      message: 'API bağlantısı',
      child: Container(
        width: 8,
        height: 8,
        margin: const EdgeInsets.only(right: 12),
        decoration: BoxDecoration(
          color: AppColors.success.withOpacity(0.8),
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppColors.success.withOpacity(0.3),
              blurRadius: 4,
            ),
          ],
        ),
      ),
    );
  }
}

/// Message list view.
class _MessageList extends StatelessWidget {
  final dynamic session;
  final ScrollController scrollController;

  const _MessageList({
    required this.session,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    final messages = session.messages;

    return ListView.builder(
      controller: scrollController,
      padding: const EdgeInsets.symmetric(vertical: 20),
      itemCount: messages.length,
      itemBuilder: (context, index) {
        return MessageBubble(message: messages[index])
            .animate()
            .fadeIn(duration: const Duration(milliseconds: 250))
            .slideY(begin: 0.05, end: 0, duration: const Duration(milliseconds: 250));
      },
    );
  }
}

/// Welcome screen when no session is active.
class _WelcomeView extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth > 800;

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Logo
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: AppColors.accent.withOpacity(0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: AppColors.accent.withOpacity(0.2),
                ),
              ),
              child: const Icon(
                Icons.balance,
                size: 36,
                color: AppColors.accent,
              ),
            ).animate().fadeIn().scale(
                  begin: const Offset(0.8, 0.8),
                  end: const Offset(1, 1),
                  duration: const Duration(milliseconds: 500),
                ),
            const SizedBox(height: 24),
            Text(
              'Hukuk AI Asistanı',
              style: Theme.of(context).textTheme.displayLarge?.copyWith(
                    color: AppColors.accent,
                  ),
            ).animate().fadeIn(delay: const Duration(milliseconds: 200)),
            const SizedBox(height: 8),
            Text(
              'Hukuki belgelerinizi yükleyin ve sorularınızı sorun',
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ).animate().fadeIn(delay: const Duration(milliseconds: 300)),
            const SizedBox(height: 40),

            // Quick action cards
            Wrap(
              spacing: 16,
              runSpacing: 16,
              alignment: WrapAlignment.center,
              children: [
                _QuickActionCard(
                  icon: Icons.upload_file,
                  title: 'Belge Yükle',
                  subtitle: 'PDF, DOCX veya RTF dosyası yükleyin',
                  onTap: () => UploadDialog.show(context),
                  isDark: isDark,
                ),
                _QuickActionCard(
                  icon: Icons.chat_bubble_outline,
                  title: 'Soru Sorun',
                  subtitle: 'Belgelerinizdeki bilgileri sorgulayın',
                  onTap: () {
                    final id = ref.read(sessionListProvider.notifier).createSession();
                    ref.read(activeSessionIdProvider.notifier).state = id;
                  },
                  isDark: isDark,
                ),
                _QuickActionCard(
                  icon: Icons.verified_user_outlined,
                  title: 'Güvenilir Yanıtlar',
                  subtitle: 'Yanıtlar yalnızca belgelerinize dayanır',
                  onTap: null,
                  isDark: isDark,
                ),
              ],
            ).animate().fadeIn(delay: const Duration(milliseconds: 400)),
          ],
        ),
      ),
    );
  }
}

class _QuickActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool isDark;

  const _QuickActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 200,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: isDark ? AppColors.darkCard : AppColors.lightCard,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.accent.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, size: 20, color: AppColors.accent),
            ),
            const SizedBox(height: 14),
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
