import SwiftUI
import AppKit
import WebKit

@MainActor
final class AppState: ObservableObject {
    @Published var selectedFolder: String = ""
    @Published var mode: String = "full"
    @Published var isRunning: Bool = false
    @Published var status: String = "Idle"
    @Published var logText: String = ""
    @Published var graphURL: URL?
    @Published var reportText: String = ""
    @Published var repoRoot: String = "/Users/joru2/Applications/Graphify"

    private var task: Process?

    init() {
        if let configured = Bundle.main.object(forInfoDictionaryKey: "GraphifyRepoRoot") as? String,
           !configured.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            repoRoot = configured
        }
    }

    func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Select"
        panel.message = "Choose a folder to analyze"

        if panel.runModal() == .OK, let url = panel.url {
            selectedFolder = url.path
            loadExistingOutputs()
        }
    }

    func run() {
        guard !selectedFolder.isEmpty else {
            status = "Select a folder first."
            return
        }
        if isRunning { return }

        let runner = "\(repoRoot)/scripts/run_graphify_native.sh"
        if !FileManager.default.isExecutableFile(atPath: runner) {
            status = "Runner not found: \(runner)"
            return
        }

        isRunning = true
        status = "Running..."
        logText = ""

        let process = Process()
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.currentDirectoryURL = URL(fileURLWithPath: repoRoot)
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-lc", "\"\(runner)\" \"\(selectedFolder)\" \(mode)"]

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            let text = String(decoding: data, as: UTF8.self)
            Task { @MainActor in
                self?.logText.append(text)
            }
        }

        process.terminationHandler = { [weak self] proc in
            Task { @MainActor in
                self?.isRunning = false
                self?.status = proc.terminationStatus == 0 ? "Completed" : "Failed (exit \(proc.terminationStatus))"
                pipe.fileHandleForReading.readabilityHandler = nil
                self?.loadExistingOutputs()
            }
        }

        do {
            try process.run()
            task = process
        } catch {
            isRunning = false
            status = "Launch error: \(error.localizedDescription)"
        }
    }

    func stop() {
        task?.terminate()
        status = "Stopped"
        isRunning = false
    }

    func openOutputFolder() {
        guard !selectedFolder.isEmpty else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: selectedFolder + "/graphify-out"))
    }

    func loadExistingOutputs() {
        guard !selectedFolder.isEmpty else { return }
        let base = URL(fileURLWithPath: selectedFolder).appendingPathComponent("graphify-out")
        let html = base.appendingPathComponent("graph.html")
        let report = base.appendingPathComponent("GRAPH_REPORT.md")

        if FileManager.default.fileExists(atPath: html.path) {
            graphURL = html
        } else {
            graphURL = nil
        }

        if let txt = try? String(contentsOf: report, encoding: .utf8) {
            reportText = txt
        } else {
            reportText = "No report yet. Run graphify first."
        }
    }
}

struct WebView: NSViewRepresentable {
    let fileURL: URL?

    func makeNSView(context: Context) -> WKWebView {
        WKWebView()
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard let url = fileURL else {
            webView.loadHTMLString("<html><body style='font-family: -apple-system; padding: 24px;'>No graph output yet.</body></html>", baseURL: nil)
            return
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }
}

struct ContentView: View {
    @StateObject private var app = AppState()

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Folder:")
                TextField("Choose folder", text: $app.selectedFolder)
                Button("Browse") { app.chooseFolder() }
            }

            HStack {
                Text("Mode:")
                Picker("Mode", selection: $app.mode) {
                    Text("Full").tag("full")
                    Text("Update").tag("update")
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 220)

                Button(app.isRunning ? "Running..." : "Run") {
                    app.run()
                }
                .disabled(app.isRunning)

                Button("Stop") { app.stop() }
                    .disabled(!app.isRunning)

                Button("Open Output") { app.openOutputFolder() }
                    .disabled(app.selectedFolder.isEmpty)

                Spacer()
                Text(app.status)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if app.isRunning {
                ProgressView()
                    .progressViewStyle(.linear)
            }

            TabView {
                ScrollView {
                    Text(app.logText.isEmpty ? "No logs yet." : app.logText)
                        .font(.system(.body, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                }
                .tabItem { Text("Logs") }

                WebView(fileURL: app.graphURL)
                    .tabItem { Text("Graph") }

                ScrollView {
                    Text(app.reportText)
                        .font(.system(.body, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                }
                .tabItem { Text("Report") }
            }
        }
        .padding(16)
        .frame(minWidth: 980, minHeight: 680)
    }
}

@main
struct GraphifyDesktopApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
