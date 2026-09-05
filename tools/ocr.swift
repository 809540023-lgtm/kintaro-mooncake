import Foundation
import Vision
import AppKit

// Usage: ocr <image path> [lang hints...]
let args = CommandLine.arguments
guard args.count >= 2 else { exit(1) }
let path = args[1]
let langs = args.count > 2 ? Array(args[2...]) : ["ja-JP", "zh-TW", "en-US"]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    fputs("cannot load image\n", stderr); exit(1)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = langs
request.usesLanguageCorrection = true
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try? handler.perform([request])
if let results = request.results {
    for obs in results {
        if let top = obs.topCandidates(1).first {
            print(top.string)
        }
    }
}
