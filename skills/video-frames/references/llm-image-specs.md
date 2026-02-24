# LLM Image Processing Specifications

Quick reference for how major LLM providers process images. Use this to choose the right preset and target-model for your use case.

## Claude (Anthropic)

- **Token formula**: `ceil(width × height / 750)`
- **Max native resolution**: 1568px per edge (auto-resizes beyond)
- **Max absolute**: 8000×8000px (rejected above)
- **Min recommended**: 200px per edge (degraded accuracy below)
- **Max megapixels**: ~1.15 MP before auto-resize
- **Multi-image limit**: >20 images → max 2000×2000 each
- **Supported formats**: JPEG, PNG, GIF, WebP
- **Max file size**: 5MB per image, 32MB per request

### Optimal dimensions for Claude

| Use case     | Dimensions | Tokens/frame |
| ------------ | ---------- | ------------ |
| Minimal cost | 768×432    | ~443         |
| Balanced     | 1024×576   | ~787         |
| Max detail   | 1568×882   | ~1,843       |
| OCR/text     | 1568×882   | ~1,843       |

## GPT-4o (OpenAI)

- **Processing pipeline**: resize to fit 2048×2048 → scale shortest side to 768px → tile into 512×512 blocks
- **Token per tile**: 170 tokens + 85 base per image
- **Low detail mode**: flat 85 tokens (ignores resolution)
- **Supported formats**: JPEG, PNG, GIF, WebP
- **Max file size**: 20MB per image

### Optimal dimensions for GPT-4o

| Use case     | Dimensions | Tiles | Tokens/frame |
| ------------ | ---------- | ----- | ------------ |
| Low detail   | any        | 0     | 85           |
| Minimal cost | 768×768    | 2×2=4 | 765          |
| Standard     | 1024×768   | 2×2=4 | 765          |
| Max useful   | 2048×768   | 4×2=8 | 1,445        |

### OCR-specific for GPT-4o

- Target 300 DPI equivalent for standard text
- Min 18px height for uppercase Latin characters
- Min 48×48px for CJK characters at 300 DPI
- Images <200×200 or >8400×8400 rejected for OCR

## Gemini 2.5 Pro

- **Small image**: both dims ≤384px → 258 tokens (minimum)
- **Tiling**: 768×768px tiles, each = 258 tokens
- **Formula**: `ceil(w/768) × ceil(h/768) × 258`
- **Max images per prompt**: 3,000
- **Supported formats**: JPEG, PNG, WebP, HEIC, HEIF
- **Max file size**: 7MB inline, 30MB from GCS

### Optimal dimensions for Gemini

| Use case     | Dimensions | Tiles | Tokens/frame |
| ------------ | ---------- | ----- | ------------ |
| Minimal cost | 384×384    | 1     | 258          |
| Single tile  | 768×768    | 1     | 258          |
| Two tiles    | 1536×768   | 2     | 516          |
| Four tiles   | 1536×1536  | 4     | 1,032        |

## Cross-Model Sweet Spots

| Preset    | Max dim | Claude     | OpenAI (high) | Gemini   | Best for                 |
| --------- | ------- | ---------- | ------------- | -------- | ------------------------ |
| efficient | 768     | ~443-786   | 255-765       | 258      | Bulk frames, long videos |
| balanced  | 1024    | ~787-1400  | 765           | 258-516  | General analysis         |
| detailed  | 1568    | ~1590-1843 | 765-1445      | 516-1032 | Fine detail needed       |
| ocr       | 1568    | ~1590-1843 | 765-1445      | 516-1032 | Text extraction          |

**Key insight**: 768px is the universal sweet spot. At this dimension:

- Claude: ~786 tokens (well under auto-resize threshold)
- OpenAI: 4 tiles = 765 tokens (efficient tile packing)
- Gemini: 1 tile = 258 tokens (minimum for useful detail)

## OCR Best Practices

1. Use `--preset ocr` which enables grayscale + high contrast + sharpening at 1568px
2. For model-specific optimization, use `--target-model claude` (1568px) for best text detail
3. Grayscale reduces file size ~60% with no OCR accuracy loss
4. High contrast (`eq=contrast=1.3`) improves text/background separation
5. Unsharp mask (`5:5:0.7`) sharpens text edges without introducing noise
