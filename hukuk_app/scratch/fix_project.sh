#!/bin/bash
PROJECT_ROOT="/Users/acar/Desktop/hukuk/hukuk_app"
MACOS_DIR="$PROJECT_ROOT/macos"
CONFIGS_DIR="$MACOS_DIR/Runner/Configs"

# 1. Update xcconfig files
cat > "$CONFIGS_DIR/Debug.xcconfig" <<EOF
#include "../../Flutter/Flutter-Debug.xcconfig"
#include "AppInfo.xcconfig"
#include "Warnings.xcconfig"
#include "Pods/Target Support Files/Pods-Runner/Pods-Runner.debug.xcconfig"
EOF

cat > "$CONFIGS_DIR/Release.xcconfig" <<EOF
#include "../../Flutter/Flutter-Release.xcconfig"
#include "AppInfo.xcconfig"
#include "Warnings.xcconfig"
#include "Pods/Target Support Files/Pods-Runner/Pods-Runner.release.xcconfig"
EOF

# Create Profile.xcconfig if missing
cat > "$CONFIGS_DIR/Profile.xcconfig" <<EOF
#include "../../Flutter/Flutter-Release.xcconfig"
#include "AppInfo.xcconfig"
#include "Warnings.xcconfig"
#include "Pods/Target Support Files/Pods-Runner/Pods-Runner.profile.xcconfig"
EOF

# 2. Update pbxproj to use these as base configurations for the target
# We need to find the buildConfiguration sections for target Runner.
# They usually have PRODUCT_NAME = hukuk_app.

# I'll just use sed to replace baseConfigurationReference for the target.
# Actually, I'll do it manually via python or similar to be safer, but I'll just use my tools.
