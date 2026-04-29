import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/models.dart';
import '../theme/app_theme.dart';

/// Elegant citation/source card displayed below AI messages.
/// Shows which document and section the answer was derived from.
class CitationCard extends StatelessWidget {
  final List<Citation> citations;

  const CitationCard({super.key, required this.citations});

  @override
  Widget build(BuildContext context) {
    if (citations.isEmpty) return const SizedBox.shrink();

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),
        // Header
        Row(
          children: [
            Icon(
              Icons.source_outlined,
              size: 14,
              color: isDark ? AppColors.textMuted : AppColors.lightTextSecondary,
            ),
            const SizedBox(width: 6),
            Text(
              'KAYNAKLAR / SOURCES',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    letterSpacing: 1.2,
                    color: isDark
                        ? AppColors.textMuted
                        : AppColors.lightTextSecondary,
                  ),
            ),
            const Spacer(),
            Text(
              '${citations.length} kaynak',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.accent,
                  ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        // Citation chips
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: citations.asMap().entries.map((entry) {
            return _CitationChip(
              citation: entry.value,
              index: entry.key + 1,
              isDark: isDark,
            ).animate().fadeIn(
                  delay: Duration(milliseconds: 100 * entry.key),
                  duration: const Duration(milliseconds: 300),
                );
          }).toList(),
        ),
      ],
    );
  }
}

class _CitationChip extends StatefulWidget {
  final Citation citation;
  final int index;
  final bool isDark;

  const _CitationChip({
    required this.citation,
    required this.index,
    required this.isDark,
  });

  @override
  State<_CitationChip> createState() => _CitationChipState();
}

class _CitationChipState extends State<_CitationChip> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final c = widget.citation;
    final bgColor = widget.isDark
        ? AppColors.citationBg
        : AppColors.citationBgLight;
    final borderColor = widget.isDark
        ? AppColors.citationBorder
        : AppColors.citationBorderLight;

    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeInOut,
        constraints: BoxConstraints(
          maxWidth: _expanded ? 500 : 280,
        ),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: borderColor, width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Top row: index badge + source + relevance
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Index badge
                Container(
                  width: 22,
                  height: 22,
                  decoration: BoxDecoration(
                    color: AppColors.accent.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Center(
                    child: Text(
                      '${widget.index}',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppColors.accent,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                // Document icon + name
                Icon(
                  _iconForDocType(c.sourceId),
                  size: 14,
                  color: AppColors.accent,
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    c.sourceId,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: widget.isDark
                              ? AppColors.textPrimary
                              : AppColors.lightTextPrimary,
                        ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                // Relevance badge
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: _relevanceColor(c.relevancePercent).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${c.relevancePercent.toStringAsFixed(0)}%',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: _relevanceColor(c.relevancePercent),
                    ),
                  ),
                ),
              ],
            ),
            // Section heading
            if (c.sectionHeading != null) ...[
              const SizedBox(height: 6),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.bookmark_outline,
                    size: 12,
                    color: widget.isDark
                        ? AppColors.textMuted
                        : AppColors.lightTextSecondary,
                  ),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      c.sectionHeading!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.accent,
                            fontWeight: FontWeight.w500,
                          ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
            // Expanded preview text
            if (_expanded && c.text.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: (widget.isDark ? Colors.black : Colors.grey.shade100)
                      .withOpacity(0.3),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  c.text.length > 300 ? '${c.text.substring(0, 300)}…' : c.text,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        height: 1.5,
                        fontSize: 11,
                        color: widget.isDark
                            ? AppColors.textSecondary
                            : AppColors.lightTextSecondary,
                      ),
                ),
              ),
            ],
            // Expand indicator
            if (!_expanded) ...[
              const SizedBox(height: 4),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.unfold_more,
                    size: 12,
                    color: widget.isDark
                        ? AppColors.textMuted
                        : AppColors.lightTextSecondary,
                  ),
                  const SizedBox(width: 2),
                  Text(
                    'Detay',
                    style: TextStyle(
                      fontSize: 10,
                      color: widget.isDark
                          ? AppColors.textMuted
                          : AppColors.lightTextSecondary,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  IconData _iconForDocType(String sourceId) {
    if (sourceId.endsWith('.pdf')) return Icons.picture_as_pdf;
    if (sourceId.endsWith('.docx')) return Icons.description;
    if (sourceId.endsWith('.rtf')) return Icons.article;
    return Icons.insert_drive_file;
  }

  Color _relevanceColor(double pct) {
    if (pct >= 80) return AppColors.success;
    if (pct >= 60) return AppColors.accent;
    return AppColors.error;
  }
}
