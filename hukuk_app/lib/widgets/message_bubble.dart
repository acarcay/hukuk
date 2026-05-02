import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/models.dart';
import '../theme/app_theme.dart';
import 'citation_card.dart';

/// Chat message bubble with role-based styling and citation display.
class MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const MessageBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final screenWidth = MediaQuery.of(context).size.width;
    final isDesktop = screenWidth > 800;

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: isDesktop ? screenWidth * 0.15 : 16,
        vertical: 6,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            _Avatar(isUser: false, isDark: isDark),
            const SizedBox(width: 12),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                // Role label
                Padding(
                  padding: const EdgeInsets.only(bottom: 6, left: 4, right: 4),
                  child: Text(
                    isUser ? 'SİZ' : 'HUKUK ASİSTANI',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          fontSize: 10,
                          letterSpacing: 1.1,
                          color: isUser
                              ? AppColors.accent
                              : (isDark
                                  ? AppColors.textMuted
                                  : AppColors.lightTextSecondary),
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                // Message content
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: isUser
                        ? AppColors.accent.withOpacity(isDark ? 0.15 : 0.08)
                        : (isDark
                            ? AppColors.darkCard
                            : AppColors.lightCard),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(20),
                      topRight: const Radius.circular(20),
                      bottomLeft: Radius.circular(isUser ? 20 : 4),
                      bottomRight: Radius.circular(isUser ? 4 : 20),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(isDark ? 0.2 : 0.05),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                    border: Border.all(
                      color: isUser
                          ? AppColors.accent.withOpacity(0.3)
                          : (isDark
                              ? AppColors.darkBorder
                              : AppColors.lightBorder),
                      width: 1,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Message text (markdown for assistant)
                      if (isUser)
                        SelectableText(
                          message.content,
                          style: Theme.of(context).textTheme.bodyLarge,
                        )
                      else
                        _AssistantContent(message: message, isDark: isDark),

                      // Streaming indicator
                      if (message.isStreaming) ...[
                        const SizedBox(height: 12),
                        _StreamingIndicator(isDark: isDark),
                      ],

                      // Citations
                      if (!isUser && message.citations.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        const Divider(height: 1),
                        const SizedBox(height: 16),
                        CitationCard(citations: message.citations),
                      ],

                      // Timing metadata
                      if (!isUser &&
                          !message.isStreaming &&
                          message.retrievalTimeMs != null) ...[
                        const SizedBox(height: 12),
                        _TimingInfo(message: message, isDark: isDark),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 12),
            _Avatar(isUser: true, isDark: isDark),
          ],
        ],
      ),
    );
  }
}

/// Avatar for user/assistant.
class _Avatar extends StatelessWidget {
  final bool isUser;
  final bool isDark;

  const _Avatar({required this.isUser, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: isUser
            ? AppColors.accent.withOpacity(0.15)
            : (isDark
                ? AppColors.darkSurfaceAlt
                : AppColors.lightSurfaceAlt),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isUser
              ? AppColors.accent.withOpacity(0.3)
              : (isDark ? AppColors.darkBorder : AppColors.lightBorder),
        ),
      ),
      child: Icon(
        isUser ? Icons.person_outline : Icons.balance,
        size: 18,
        color: isUser
            ? AppColors.accent
            : (isDark ? AppColors.textSecondary : AppColors.lightTextSecondary),
      ),
    );
  }
}

/// Renders assistant content as Markdown.
class _AssistantContent extends StatelessWidget {
  final ChatMessage message;
  final bool isDark;

  const _AssistantContent({required this.message, required this.isDark});

  @override
  Widget build(BuildContext context) {
    if (message.content.isEmpty && message.isStreaming) {
      return const SizedBox(height: 20);
    }

    return MarkdownBody(
      data: message.content,
      selectable: true,
      styleSheet: MarkdownStyleSheet(
        p: Theme.of(context).textTheme.bodyLarge,
        h1: Theme.of(context).textTheme.headlineMedium,
        h2: Theme.of(context).textTheme.titleLarge,
        strong: Theme.of(context).textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.w700,
            ),
        em: Theme.of(context).textTheme.bodyLarge?.copyWith(
              fontStyle: FontStyle.italic,
            ),
        code: TextStyle(
          fontFamily: 'JetBrains Mono',
          fontSize: 13,
          color: AppColors.accent,
          backgroundColor:
              isDark ? AppColors.darkSurfaceAlt : AppColors.lightSurfaceAlt,
        ),
        blockquoteDecoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: AppColors.accent.withOpacity(0.5),
              width: 3,
            ),
          ),
        ),
      ),
    );
  }
}

/// Pulsing dots indicator while streaming.
class _StreamingIndicator extends StatelessWidget {
  final bool isDark;

  const _StreamingIndicator({required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) {
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 2),
          child: Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: AppColors.accent.withOpacity(0.6),
              shape: BoxShape.circle,
            ),
          )
              .animate(
                onPlay: (c) => c.repeat(reverse: true),
              )
              .scaleXY(
                begin: 0.5,
                end: 1.0,
                delay: Duration(milliseconds: 200 * i),
                duration: const Duration(milliseconds: 600),
                curve: Curves.easeInOut,
              ),
        );
      }),
    );
  }
}

/// Shows retrieval + generation timing below assistant messages.
class _TimingInfo extends StatelessWidget {
  final ChatMessage message;
  final bool isDark;

  const _TimingInfo({required this.message, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final muted = isDark ? AppColors.textMuted : AppColors.lightTextSecondary;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.timer_outlined, size: 11, color: muted),
        const SizedBox(width: 4),
        Text(
          'Arama: ${message.retrievalTimeMs?.toStringAsFixed(0)}ms'
          ' · Üretim: ${message.generationTimeMs?.toStringAsFixed(0)}ms',
          style: TextStyle(fontSize: 10, color: muted),
        ),
        if (message.model != null) ...[
          Text(' · ', style: TextStyle(fontSize: 10, color: muted)),
          Text(
            message.model!,
            style: TextStyle(fontSize: 10, color: muted),
          ),
        ],
      ],
    );
  }
}
