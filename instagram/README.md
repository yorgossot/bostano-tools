# instagram

Post photos, reels, and carousels to Instagram from local files. The `.env` is already configured.

## CLI Usage

```bash
cd /root/openclaw-agents/bostano/.openclaw/projects/bostano-tools/instagram
python3 instagram.py <command> [options]
```

## Commands

### post-photo

```bash
python3 instagram.py post-photo --path /tmp/photo.jpg --caption "Hello world"
```

### post-reel

```bash
python3 instagram.py post-reel --path /tmp/clip.mp4 --caption "New reel"
```

### post-carousel

2-10 items, order preserved. Prefix each item with `image:` or `video:`.

```bash
python3 instagram.py post-carousel \
  --item image:/tmp/a.jpg \
  --item video:/tmp/b.mp4 \
  --item image:/tmp/c.jpg \
  --caption "Swipe"
```

### get-media

```bash
python3 instagram.py get-media --limit 5
```

### get-media-info

```bash
python3 instagram.py get-media-info --id 12345678
```

## Output

All commands print JSON to stdout. Posting commands return `{"media_id": "..."}`. Query commands return the full API response.

All paths must be absolute. Exits non-zero on failure with error message on stderr.
