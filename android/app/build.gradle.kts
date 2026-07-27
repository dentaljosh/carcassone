import javax.inject.Inject
import org.gradle.process.ExecOperations

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// ---------------------------------------------------------------------------
// Python bundle sync (repo -> app/build/python)
//
// `android/tools/sync_python.py` is owned by a sibling workstream. Contract:
//     python3 tools/sync_python.py --repo <repo_root> --out <dest_dir>
// It populates <dest_dir> with carcassonne_ai/, wingedsheep/ and the top-level
// modules. If the script is not present yet, this task WARNS and skips so the
// skeleton still builds standalone.
// ---------------------------------------------------------------------------

val repoRoot: File = rootProject.projectDir.parentFile          // .../carcassone
val syncScript: File = rootProject.file("tools/sync_python.py")
// NOTE: NOT build/python — Chaquopy's own installPythonRequirements task owns
// that directory, and sharing it makes Gradle fail the build with an implicit
// -dependency validation error.
val pythonBundleDir: Provider<Directory> = layout.buildDirectory.dir("generated/pythonBundle")

abstract class SyncPythonFromRepo @Inject constructor(
    private val execOps: ExecOperations,
) : DefaultTask() {

    @get:Internal abstract val script: RegularFileProperty
    @get:Internal abstract val repo: DirectoryProperty
    @get:OutputDirectory abstract val outDir: DirectoryProperty
    @get:Input abstract val interpreter: Property<String>

    @TaskAction
    fun run() {
        val scriptFile = script.get().asFile
        val dest = outDir.get().asFile
        if (!scriptFile.isFile) {
            dest.mkdirs()
            logger.warn(
                "[syncPythonFromRepo] SKIPPED: ${scriptFile.path} does not exist yet. " +
                    "The APK will be built WITHOUT the repo Python bundle " +
                    "(only android/app/src/main/python will be packaged)."
            )
            return
        }
        dest.mkdirs()
        logger.lifecycle("[syncPythonFromRepo] ${scriptFile.name} --repo ${repo.get().asFile} --out $dest")
        execOps.exec {
            commandLine(
                interpreter.get(), scriptFile.absolutePath,
                "--repo", repo.get().asFile.absolutePath,
                "--out", dest.absolutePath,
            )
        }
    }
}

val syncPythonFromRepo by tasks.registering(SyncPythonFromRepo::class) {
    group = "build"
    description = "Sync the repo's Python packages into the Chaquopy source set."
    script.set(syncScript)
    repo.set(repoRoot)
    outDir.set(pythonBundleDir)
    interpreter.set("/usr/bin/python3.12")
    // Cheap file copy; always re-run so an edit in src/ is never stale in the APK.
    outputs.upToDateWhen { false }
}

tasks.named("preBuild") { dependsOn(syncPythonFromRepo) }

// preBuild ordering alone does not guarantee Chaquopy's source-merge tasks see a
// populated dir, so wire them explicitly too.
tasks.matching { t ->
    t.name != "syncPythonFromRepo" &&
        t.name.contains("Python") &&
        (t.name.startsWith("merge") || t.name.startsWith("generate"))
}.configureEach { dependsOn(syncPythonFromRepo) }

android {
    namespace = "com.jishal.carcassonne"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jishal.carcassonne"
        // Chaquopy 17 requires >= 24; 26 keeps us clear of legacy multidex/ART quirks.
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1-m0"

        ndk {
            // Chaquopy's Python 3.12+ runtime ships 64-bit ABIs only.
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

chaquopy {
    defaultConfig {
        // Must match buildPython's major.minor (Chaquopy 17 breaking change).
        version = "3.12"
        buildPython("/usr/bin/python3.12")

        pip {
            install("numpy")
            install("pyyaml")
        }

        // Extracted to the filesystem so Path(__file__)-relative data loads
        // (e.g. the bundled PRODUCTION.yaml) work.
        extractPackages("carcassonne_ai")
    }

    // Appends to the default src/main/python (which the sibling workstream owns).
    sourceSets {
        getByName("main") {
            srcDir(pythonBundleDir)
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.1")

    val composeBom = platform("androidx.compose:compose-bom:2025.04.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
