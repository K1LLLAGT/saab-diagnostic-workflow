# ANDRAX 2.0 App — Build Notes

The `src/` tree is a **skeleton** meant to be dropped into a standard Gradle
Android project. It intentionally ships only the source that is unique to
ANDRAX so you can wire it into the build system of your choice.

## Minimum project files to add

Create these around `src/` to make it buildable in Android Studio:

```
android-app/
├── build.gradle.kts          # module build file (below)
├── settings.gradle.kts
├── gradle/ ...                # wrapper
└── src/main/
    ├── AndroidManifest.xml    # provided
    ├── assets/tool_registry.json   # provided (copy of the backend registry)
    ├── java/com/andrax/two/...     # provided
    └── res/
        ├── values/themes.xml  # define Theme.Andrax (below)
        └── mipmap-*/ic_launcher…    # any launcher icon
```

### `build.gradle.kts` (module)

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.andrax.two"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.andrax.two"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "2.0.0"
    }
    buildTypes {
        release { isMinifyEnabled = false }
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    // org.json ships with the Android platform — no dependency needed.
}
```

### `res/values/themes.xml`

```xml
<resources>
    <style name="Theme.Andrax" parent="Theme.AppCompat.DayNight.DarkActionBar" />
</resources>
```

## Build & install

```sh
./gradlew assembleDebug
./gradlew installDebug      # onto the device that also runs Termux
```

## Optional: Jetpack Compose version of ToolDetail

If you prefer Compose, the detail screen collapses to:

```kotlin
@Composable
fun ToolDetail(tool: Tool, onRun: (List<String>) -> Unit) {
    var args by remember { mutableStateOf("") }
    Column(Modifier.padding(16.dp)) {
        Text(tool.name, style = MaterialTheme.typography.headlineSmall)
        Text(tool.description)
        Spacer(Modifier.height(8.dp))
        Text("andrax ${tool.example}", style = MaterialTheme.typography.bodySmall)
        OutlinedTextField(args, { args = it }, label = { Text("Arguments") })
        Button(onClick = { onRun(args.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }) }) {
            Text("Run in Termux")
        }
    }
}
```

`onRun` would call `TermuxLauncher.runTool(context, tool.id, it)`.

## Sync the catalog after backend changes

```sh
cp ../launcher-system/tool_registry.json src/main/assets/tool_registry.json
```
