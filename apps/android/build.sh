#!/usr/bin/env bash
# Construit l'APK « Mission Control » sans Gradle (aapt2 + javac + d8 + apksigner).
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_HOME:-$HOME/Android/Sdk}; BT=$SDK/build-tools/35.0.0; JAR=$SDK/platforms/android-35/android.jar
export JAVA_HOME=${JAVA_HOME:-$HOME/jdk-17.0.19+10}; export PATH=$JAVA_HOME/bin:$PATH
KS=${KEYSTORE:-$HOME/.local/share/arpagona/android/arpagona-release.jks}
rm -rf build && mkdir -p build/res build/classes build/dex
"$BT/aapt2" compile --dir res -o build/res/res.zip
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -o build/unsigned.apk build/res/res.zip --java build/gen
javac -source 17 -target 17 -classpath "$JAR" -d build/classes $(find src build/gen -name '*.java')
"$BT/d8" --min-api 26 --lib "$JAR" --output build/dex $(find build/classes -name '*.class')
(cd build/dex && zip -q -u ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 build/unsigned.apk build/aligned.apk
if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"; chmod 700 "$(dirname "$KS")"
  head -c 24 /dev/urandom | base64 | tr -d '/+=' > "$KS.pass"; chmod 600 "$KS.pass"
  keytool -genkeypair -keystore "$KS" -alias arpagona -keyalg RSA -keysize 3072 -validity 10000 \
    -storepass:file "$KS.pass" -dname "CN=ARPAGONA, O=ARPAGONA, C=FR" >/dev/null
  chmod 600 "$KS"
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass "file:$KS.pass" --ks-key-alias arpagona --out build/MissionControl-ARPAGONA.apk build/aligned.apk
"$BT/apksigner" verify --print-certs build/MissionControl-ARPAGONA.apk | head -2
ls -la build/MissionControl-ARPAGONA.apk
