import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';

/// Chat input bar with send button and upload trigger.
class ChatInput extends ConsumerStatefulWidget {
  final VoidCallback? onUploadTap;

  const ChatInput({super.key, this.onUploadTap});

  @override
  ConsumerState<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends ConsumerState<ChatInput> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    ref.read(chatControllerProvider).sendMessage(text);
    _controller.clear();
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final isStreaming = ref.watch(isStreamingProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 15, sigmaY: 15),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          decoration: BoxDecoration(
            color: isDark ? AppColors.darkSurface.withOpacity(0.4) : AppColors.lightSurface.withOpacity(0.8),
            border: Border(
              top: BorderSide(
                color: isDark ? AppColors.accent.withOpacity(0.2) : AppColors.lightBorder,
                width: 1,
              ),
            ),
          ),
          child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            // Upload button
            IconButton(
              onPressed: isStreaming ? null : widget.onUploadTap,
              icon: const Icon(Icons.attach_file_rounded),
              tooltip: 'Belge Yükle',
              style: IconButton.styleFrom(
                foregroundColor: AppColors.accent,
                backgroundColor: AppColors.accent.withOpacity(0.1),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
            const SizedBox(width: 10),
            // Text field
            Expanded(
              child: KeyboardListener(
                focusNode: FocusNode(),
                onKeyEvent: (event) {
                  if (event is KeyDownEvent &&
                      event.logicalKey == LogicalKeyboardKey.enter &&
                      !HardwareKeyboard.instance.isShiftPressed) {
                    _send();
                  }
                },
                child: TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  maxLines: 5,
                  minLines: 1,
                  enabled: !isStreaming,
                  textInputAction: TextInputAction.newline,
                  decoration: InputDecoration(
                    hintText: isStreaming
                        ? 'Yanıt oluşturuluyor…'
                        : 'Hukuki sorunuzu yazın…',
                    suffixIcon: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 200),
                      child: isStreaming
                          ? Padding(
                              padding: const EdgeInsets.all(12),
                              child: SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppColors.accent,
                                ),
                              ),
                            )
                          : IconButton(
                              onPressed: _send,
                              icon: const Icon(Icons.send_rounded),
                              color: AppColors.accent,
                              tooltip: 'Gönder',
                            ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    ));
  }
}
