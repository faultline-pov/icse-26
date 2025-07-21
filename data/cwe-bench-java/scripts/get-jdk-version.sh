#!/bin/bash

# --- Detect version from pom.xml ---
detect_from_pom() {
  if [[ -f "pom.xml" ]]; then
    grep -Eo '<(java\.version|maven\.compiler\.source|source)>\s*[0-9]+(\.[0-9]+)?\s*</' pom.xml \
      | head -1 \
      | grep -Eo '[0-9]+(\.[0-9]+)?'
  fi
}

# --- Detect version from build.gradle ---
detect_from_gradle() {
  if [[ -f "build.gradle" ]]; then
    grep -E 'languageVersion\s*=\s*JavaLanguageVersion\.of\([0-9]+' build.gradle \
      | grep -oE '[0-9]+' | head -1 && return

    grep -E 'sourceCompatibility\s*=\s*JavaVersion\.VERSION_' build.gradle \
      | grep -oE '[0-9]+' | head -1
  fi
}

# --- Determine Java version ---
version=$(detect_from_pom)

if [ -z "$version" ]; then
  version=$(detect_from_gradle)
fi

if [ -z "$version" ]; then
  echo "⚠️  Java version not found in pom.xml or build.gradle."
  exit 1
fi

# --- Normalize Java version ---
if [[ "$version" == "1.8" ]]; then
  version="8"
elif [[ "$version" == "1.7" ]]; then
  version="7"
elif [[ "$version" == "1.6" ]]; then
  version="6"
fi

echo $version