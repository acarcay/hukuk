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

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkSurface : AppColors.lightSurface,
        border: Border(
          top: BorderSide(
            color: isDark ? AppColors.darkBorder : AppColors.lightBorder,
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
    );
  }
}
