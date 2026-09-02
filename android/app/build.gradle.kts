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

// ⚠️ SHARED BUILD SCRIPTS — an input to BOTH wheel tasks (ROUND2 F-4, 2026-08-02).
// The P7 refactor moved MAX_PAGE_SIZE, PAGE_ALIGN_LDFLAG, TARGET_ARTIFACT_VERSION,
// ANDROID_API, ensure_target, the ELF gate and write_wheel into
// `android/tools/_chaquopy_common.py`, and `build_config.py` owns the cy module list —
// but neither task declared them, so a change to either left Gradle marking the other
// task UP-TO-DATE. Concrete path that shipped mismatched wheels: bump MAX_PAGE_SIZE,
// cy's version moves and buildCyWheels reruns, buildRustWheels does NOT, and the APK
// carries a cy wheel at the new alignment beside a rust wheel at the old one. Declared
// on BOTH tasks so shared codegen changes rebuild them TOGETHER.
val sharedWheelScripts: List<File> = listOf(
    rootProject.file("tools/_chaquopy_common.py"),
    repoRoot.resolve("android/native/carc-cy/build_config.py"),
)

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
    // The shared build machinery (see sharedWheelScripts) — half the codegen lives
    // there, so it is as much an input as the .pyx.
    @get:InputFiles abstract val shared: ConfigurableFileCollection
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
    shared.setFrom(sharedWheelScripts)
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
// Rust engine+search core (carc-rs) -> prebuilt Android wheels                [P7]
//
// Same Chaquopy constraint as buildCyWheels above (v17 cannot compile native code),
// so `tools/build_rust_wheels.py` cross-compiles rust/carc's PyO3 module `carc_rs`
// with the NDK linker and drops one wheel per ABI into a --find-links directory.
//
// This wheel is OPT-IN AT RUNTIME. `android_bridge` defaults to the Python engine
// and only touches carc_rs when the backend flag selects it, so shipping the wheel
// changes nothing about what the app plays. If no NDK (or no cargo) is installed the
// requirement is simply omitted and the flag's rust path reports unavailable.
// ---------------------------------------------------------------------------
val rustBuildScript: File = rootProject.file("tools/build_rust_wheels.py")
val rustWheelDir: Provider<Directory> = layout.buildDirectory.dir("generated/rustWheels")
val rustCrateDir: File = repoRoot.resolve("rust/carc")

// cargo must be on PATH at CONFIGURATION time for the version probe to work; a
// checkout without a Rust toolchain degrades exactly like a checkout without an NDK.
val cargoPresent: Boolean = runCatching {
    providers.exec { commandLine("cargo", "--version") }.result.get().exitValue == 0
}.getOrDefault(false)

val rustEnabled: Boolean =
    rustBuildScript.isFile && cyNdkDir != null && rustCrateDir.isDirectory && cargoPresent

// Content-addressed over the whole Rust tree, asked of the build script so the
// hashing rule lives in exactly ONE place (same contract as cyVersion).
val rustVersion: String? = if (!rustEnabled) null else providers.exec {
    commandLine(buildPythonPath, rustBuildScript.absolutePath, "--print-version")
}.standardOutput.asText.get().trim()

abstract class BuildRustWheels @Inject constructor(
    private val execOps: ExecOperations,
) : DefaultTask() {

    @get:InputFile abstract val script: RegularFileProperty
    @get:InputFiles abstract val sources: ConfigurableFileCollection
    // Same reason as BuildCyWheels.shared — see sharedWheelScripts (ROUND2 F-4).
    @get:InputFiles abstract val shared: ConfigurableFileCollection
    @get:Input abstract val interpreter: Property<String>
    @get:Input abstract val version: Property<String>
    @get:Input abstract val sdkDir: Property<String>
    @get:Input abstract val jobs: Property<Int>
    @get:OutputDirectory abstract val outDir: DirectoryProperty

    @TaskAction
    fun run() {
        logger.lifecycle("[buildRustWheels] carc-rs==${version.get()} -> ${outDir.get().asFile}")
        execOps.exec {
            commandLine(
                interpreter.get(), script.get().asFile.absolutePath,
                "--out", outDir.get().asFile.absolutePath,
                "--version", version.get(),
                "--sdk-dir", sdkDir.get(),
                "--jobs", jobs.get().toString(),
            )
        }
    }
}

val buildRustWheels by tasks.registering(BuildRustWheels::class) {
    group = "build"
    description = "Cross-compile the Rust engine+search core (carc_rs) into Android wheels."
    onlyIf { rustEnabled }
    script.set(rustBuildScript)
    // Only the files whose bytes can change the compiled module. The include list is
    // the build script's own VERSION_SUFFIXES and the excludes are its
    // `_chaquopy_common.VERSION_EXCLUDE_DIRS` — a parity claim that was FALSE until
    // 2026-08-02 (REVIEW.md #8: the script hashed `target/**` and
    // `.chaquopy-cache/**` that this fileTree already excluded). Keep the two lists
    // equal; VERSION_EXCLUDE_DIRS is the one to edit first.
    sources.setFrom(
        project.fileTree(rustCrateDir) {
            include("**/*.rs", "**/*.toml", "**/*.lock")
            exclude("target/**", ".chaquopy-cache/**")
        }
    )
    shared.setFrom(sharedWheelScripts)
    interpreter.set(buildPythonPath)
    version.set(rustVersion ?: "0")
    sdkDir.set(androidSdkDir.absolutePath)
    jobs.set(4)
    outDir.set(rustWheelDir)
}

if (!rustEnabled) {
    logger.warn(
        "[buildRustWheels] SKIPPED: " +
            (if (!cargoPresent) "no `cargo` on PATH. " else "") +
            (if (cyNdkDir == null) "no Android NDK under ${androidSdkDir.resolve("ndk")}. " else "") +
            "The APK ships WITHOUT carc_rs; android_bridge's rust backend flag will " +
            "report the backend unavailable and the app keeps playing the Python path " +
            "(which is the default regardless)."
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

tasks.named("preBuild") {
    dependsOn(syncPythonFromRepo, checkTileAssets, buildCyWheels, buildRustWheels)
}

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
    t.name != "buildCyWheels" && t.name != "buildRustWheels" &&
        t.name.contains("Python") &&
        (t.name.contains("Requirements") || t.name.startsWith("generate") || t.name.startsWith("merge"))
}.configureEach { dependsOn(buildCyWheels, buildRustWheels) }

android {
    namespace = "com.jishal.carcassonne"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jishal.carcassonne"
        // Chaquopy 17 requires >= 24; 26 keeps us clear of legacy multidex/ART quirks.
        minSdk = 26
        targetSdk = 35
        // Bumped 2 -> 3 for the REMOTE-OPPONENT build (2026-08-30). The only
        // shipped changes are Kotlin/bridge: the Settings opponent selector, the
        // HTTP client, INTERNET + cleartext in the manifest, and the archive's
        // `opponent` label. The champion path is byte-identical (OpponentModeTest
        // pins the `new_game` JSON literally), so an E4 game played on this build
        // is the same measurement as one played on versionCode 2.
        // Bumped 3 -> 4 for the M3 UI build (2026-09-02). ⛔ NOT A PLAY EPOCH.
        // The champion, its budget, the rules profile and the tie-arbiter config
        // are untouched: `newGameConfig` still emits the byte-identical champion
        // JSON (OpponentModeTest pins it literally), and no file under src/,
        // engine/, rust/ or governance/ changed. What changed is the screen — the
        // opponent's face-up tile and an opt-in next-tile peek during its turn, a
        // foreground service so the turn keeps full CPU when backgrounded, tile-bag
        // grouping by the engine's own tile identity, a fail-loud asset loader, and
        // a copy audit. An E4 game played on this build is the same measurement as
        // one played on versionCode 3 EXCEPT for the peek, which is why a game that
        // used it is stamped `preview_next_tile: true` in the archive rather than
        // left to be inferred from a build date.
        // Bumped 4 -> 5 for the two owner rulings of 2026-09-02 ("22k each. fix the
        // labels."). Still NOT a play epoch against versionCode 4: the champion,
        // its budget, the rules profile and the tie-arbiter config are unchanged,
        // and no file under src/, engine/, rust/ or governance/ moved. The only
        // BEHAVIOURAL change is to remote games, whose archive `opponent` stamp is
        // now derived from the server's own /health label instead of being the
        // hardcoded "carcasum_remote_5000ms" — so a remote archive from this build
        // names the opponent that actually played. Champion archives are byte-for-
        // byte what versionCode 4 wrote.
        versionCode = 5
        versionName = "0.1-m3-ui.1"

        // Instrumented tests are the ONLY surface that can run code inside the
        // app's Chaquopy environment (numpy + the carc_rs wheel as pip resolved
        // it) without adding a debug hook to the shipping app. G7's device legs
        // live in app/src/androidTest — see RustPortDeviceTest.kt.
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

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
            // The Rust core (P7). Shipped but INERT unless android_bridge's backend
            // flag selects it — see buildRustWheels above.
            if (rustEnabled) {
                options("--find-links", rustWheelDir.get().asFile.absolutePath)
                install("carc-rs==$rustVersion")
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
    // Instrumented (on-device) tests — the G7 device legs.
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test:rules:1.6.1")
    // The platform's org.json is a stub in JVM unit tests ("not mocked"); the real
    // implementation on the test classpath lets DifficultyTest assert the actual
    // new_game config JSON rather than just the enum fields.
    testImplementation("org.json:json:20240303")
}
