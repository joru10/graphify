// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "GraphifyDesktop",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "GraphifyDesktop", targets: ["GraphifyDesktop"])
    ],
    targets: [
        .executableTarget(
            name: "GraphifyDesktop",
            path: "Sources/GraphifyDesktop"
        )
    ]
)
