import java.util.Properties
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

// The interpreter used for BOTH the bundle sync and Chaquopy's own buildPython.
// Machine-local, so it comes from local.properties (untracked) with the CI/dev
// default as the fallback. See android/README.md "Prerequisites".
val buildPythonPath: String = run {
    val props = Properties()
    val f = rootProject.file("local.properties")
    if (f.isFile) f.inputStream().use { props.load(it) }
    props.getProperty("chaquopy.buildPython") ?: "/usr/bin/python3.12"
}
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
    interpreter.set(buildPythonPath)
    // Cheap file copy; always re-run so an edit in src/ is never stale in the APK.
    outputs.upToDateWhen { false }
}

// ---------------------------------------------------------------------------
// Cython fast paths (carc-cy) -> prebuilt Android wheels
//
// Chaquopy 17 CANNOT compile native code: its pip wrapper always runs
//   pip install --only-binary :all: --platform android_<minSdk>_<abi>
// so a source dir with a C/Cython extension dies with
//   "error: CCompiler.compile: Chaquopy cannot compile native code".
// The only supported route is to hand pip a FINISHED Android wheel, so
// `tools/build_cy_wheels.py` cross-compiles src/carcassonne_ai/*.pyx with NDK clang
// and drops one wheel per ABI into a --find-links directory.
//
// If no NDK is installed we simply omit the requirement: flat_leaf.py / board_repr.py
// both fall back to pure Python on ImportError, so the app still works (just slower).
// ---------------------------------------------------------------------------
val cyBuildScript: File = rootProject.file("tools/build_cy_wheels.py")
val cyWheelDir: Provider<Directory> = layout.buildDirectory.dir("generated/cyWheels")
val cyPyxSources: List<File> =
    listOf("flat_leaf_cy", "flat_repr_cy").map { repoRoot.resolve("src/carcassonne_ai/$it.pyx") }

val androidSdkDir: File = run {
    val props = Properties()
    val f = rootProject.file("local.properties")
    if (f.isFile) f.inputStream().use { props.load(it) }
    val p = props.getProperty("sdk.dir")
        ?: System.getenv("ANDROID_HOME")
        ?: "${System.getProperty("user.home")}/Android/Sdk"
    File(p)
}

// Highest installed side-by-side NDK, or an env override. Null => skip the wheels.
val cyNdkDir: File? = sequenceOf(System.getenv("ANDROID_NDK_HOME"), System.getenv("ANDROID_NDK_ROOT"))
    .filterNotNull().map { File(it) }.firstOrNull { it.isDirectory }
    ?: androidSdkDir.resolve("ndk").listFiles()?.filter { it.isDirectory }?.maxByOrNull { it.name }

val cyEnabled: Boolean =
    cyBuildScript.isFile && cyNdkDir != null && cyPyxSources.all { it.isFile }

// Content-addressed version, asked of the build script itself so the hashing rule lives
// in exactly ONE place. Any .pyx edit changes this string, which changes the pip
// requirement, which invalidates Chaquopy's task inputs -- so a stale wheel can never be
// served out of pip's cache after a source edit.
val cyVersion: String? = if (!cyEnabled) null else providers.exec {
    commandLine(buildPythonPath, cyBuildScript.absolutePath, "--print-version")
}.standardOutput.asText.get().trim()

abstract class BuildCyWheels @Inject constructor(
    private val execOps: ExecOperations,
) : DefaultTask() {

    @get:InputFile abstract val script: RegularFileProperty
    @get:InputFiles abstract val pyx: ConfigurableFileCollection
    @get:Input abstract val interpreter: Property<String>
    @get:Input abstract val version: Property<String>
    @get:Input abstract val sdkDir: Property<String>
    @get:OutputDirectory abstract val outDir: DirectoryProperty

    @TaskAction
    fun run() {
        logger.lifecycle("[buildCyWheels] carc-cy==${version.get()} -> ${outDir.get().asFile}")
        execOps.exec {
            commandLine(
                interpreter.get(), script.get().asFile.absolutePath,
                "--out", outDir.get().asFile.absolutePath,
                "--version", version.get(),
                "--sdk-dir", sdkDir.get(),
            )
        }
    }
}

val buildCyWheels by tasks.registering(BuildCyWheels::class) {
    group = "build"
    description = "Cross-compile the repo's Cython fast paths into Android wheels."
    onlyIf { cyEnabled }
    script.set(cyBuildScript)
    pyx.setFrom(cyPyxSources)
    interpreter.set(buildPythonPath)
    version.set(cyVersion ?: "0")
    sdkDir.set(androidSdkDir.absolutePath)
    outDir.set(cyWheelDir)
}

if (!cyEnabled) {
    logger.warn(
        "[buildCyWheels] SKIPPED: no Android NDK found under ${androidSdkDir.resolve("ndk")}. " +
            "The APK will run the PURE-PYTHON leaf and board encoder (correct, ~1.5-2.5x slower " +
            "on the leaf+repr share of move time). Install one with: " +
            "sdkmanager --install 'ndk;27.3.13750724'"
    )
}

// ---------------------------------------------------------------------------
// Tile-art gate
//
// `app/src/main/assets/tiles/` is gitignored (generated art, not source), so a
// clean clone has NO tile PNGs and would happily build a tile-less APK that only
// fails once it is on a phone. This task turns that into a build error with the
// exact command to run. It deliberately does NOT invoke prepare_assets.py itself:
// that needs Pillow in a venv Gradle knows nothing about.
// ---------------------------------------------------------------------------
val tileAssetsDir: File = file("src/main/assets/tiles/base_game")
val expectedTileCount = 32

abstract class CheckTileAssets : DefaultTask() {
    @get:Internal abstract val dir: DirectoryProperty
    @get:Input abstract val expected: Property<Int>

    @TaskAction
    fun run() {
        val d = dir.get().asFile
        val found = d.listFiles { f -> f.isFile && f.name.endsWith(".png") }?.size ?: 0
        if (found < expected.get()) {
            throw GradleException(
                """
                |Tile art is missing: found $found of ${expected.get()} PNGs in
                |  ${d.path}
                |
                |These assets are generated, not checked in (see .gitignore), so a fresh
                |clone has to build them once:
                |
                |  .venv/bin/python android/tools/prepare_assets.py
                |
                |(needs Pillow: .venv/bin/pip install pillow)
                """.trimMargin()
            )
        }
    }
}

val checkTileAssets by tasks.registering(CheckTileAssets::class) {
    group = "verification"
    description = "Fail early if the generated tile art is missing from assets/."
    dir.set(tileAssetsDir)
    expected.set(expectedTileCount)
    outputs.upToDateWhen { false }
}

tasks.named("preBuild") { dependsOn(syncPythonFromRepo, checkTileAssets, buildCyWheels) }

// preBuild ordering alone does not guarantee Chaquopy's source-merge tasks see a
// populated dir, so wire them explicitly too.
tasks.matching { t ->
    t.name != "syncPythonFromRepo" &&
        t.name.contains("Python") &&
        (t.name.startsWith("merge") || t.name.startsWith("generate"))
}.configureEach { dependsOn(syncPythonFromRepo) }

// The wheels must exist before Chaquopy's pip runs against --find-links. That is the
// `...PythonRequirements` task; the generate/merge ones are wired for good measure.
tasks.matching { t ->
    t.name != "buildCyWheels" &&
        t.name.contains("Python") &&
        (t.name.contains("Requirements") || t.name.startsWith("generate") || t.name.startsWith("merge"))
}.configureEach { dependsOn(buildCyWheels) }

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
            // arm64-v8a = phones, x86_64 = emulator.
            //
            // ⚠️ This CANNOT be narrowed per build type, though it would be worth ~8 MB
            // of release APK to drop x86_64. Two AGP/Chaquopy facts block every version
            // of that change, both verified here by building and unzipping the APKs:
            //   1. defaultConfig and buildType `abiFilters` are UNIONed, never
            //      subtracted — a `release { ndk { abiFilters.clear() } }` is a no-op on
            //      its own empty set and x86_64 still shipped.
            //   2. Inverting it (narrow default, `debug` widens) configures cleanly and
            //      silently produces a BROKEN debug APK: Chaquopy reads this
            //      defaultConfig list alone when it resolves wheels and generates
            //      assets/chaquopy/bootstrap-native/, so debug got AGP's x86_64 .so
            //      files with no x86_64 CPython or numpy behind them.
            // Chaquopy takes ABI overrides only per product FLAVOR, and adding a flavour
            // dimension renames every task (assembleDebug -> assemble<Flavour>Debug).
            // Not worth it while the release build is a local artefact.
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
        buildPython(buildPythonPath)

        pip {
            // Prebuilt Cython fast paths, one wheel per ABI (see buildCyWheels above).
            // --find-links (NOT --extra-index-url: v17 dropped local paths there) plus an
            // exact == pin, so the requirement string itself changes whenever a .pyx does.
            if (cyEnabled) {
                options("--find-links", cyWheelDir.get().asFile.absolutePath)
                install("carc-cy==$cyVersion")
            }
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
    // Persists the difficulty preset (SettingsStore). Preferences-only — no
    // proto codegen, so no extra plugin.
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    val composeBom = platform("androidx.compose:compose-bom:2025.04.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.foundation:foundation")
    // Declared explicitly rather than leaned on transitively: GameScreen's
    // auto-recentre uses `animate()` from animation-core.
    implementation("androidx.compose.animation:animation-core")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // JVM unit tests cover BoardGeometry only — the board <-> screen transform,
    // hit-testing and fit math. Everything else on the game path needs a device.
    testImplementation("junit:junit:4.13.2")
    // The platform's org.json is a stub in JVM unit tests ("not mocked"); the real
    // implementation on the test classpath lets DifficultyTest assert the actual
    // new_game config JSON rather than just the enum fields.
    testImplementation("org.json:json:20240303")
}
