# instagram

Post photos, reels, and carousels to Instagram from local files. The `.env` is already configured.

```python
import sys
sys.path.insert(0, "/root/openclaw-agents/bostano/.openclaw/projects/bostano-tools/instagram")
from instagram import InstagramClient

client = InstagramClient()
```

## Methods

| Method | Args | Returns |
|---|---|---|
| `post_photo(path, caption="")` | absolute path to `.jpg`/`.png` | media ID `str` |
| `post_reel(path, caption="")` | absolute path to `.mp4` | media ID `str` |
| `post_carousel(items, caption="")` | list of `{"image_path": "..."}` or `{"video_path": "..."}` dicts, 2-10 items | media ID `str` |
| `get_media(limit=10)` | | `list[dict]` with keys: `id`, `caption`, `media_type`, `timestamp`, `permalink` |
| `get_media_info(media_id)` | media ID string | `dict` with keys: `id`, `caption`, `media_type`, `timestamp`, `permalink`, `like_count`, `comments_count` |

## Examples

```python
# Single photo
media_id = client.post_photo("/tmp/photo.jpg", caption="Hello world")

# Carousel
media_id = client.post_carousel(
    items=[{"image_path": "/tmp/a.jpg"}, {"image_path": "/tmp/b.jpg"}],
    caption="Swipe",
)

# Check recent posts
posts = client.get_media(limit=5)
```

All paths must be absolute. Raises `requests.exceptions.HTTPError` on API failure, `RuntimeError` on container processing failure.
