"""
Elementary Instagram Graph API controls.
Covers: photo post, reel post, carousel post, status check, media list.
Local files are uploaded to a temporary host to obtain a public URL,
which is then passed to the Instagram API.

Requires env var (or pass directly):
  INSTAGRAM_ACCESS_TOKEN
"""

import os
import time
import requests
from dotenv import load_dotenv

GRAPH_BASE = "https://graph.instagram.com/v22.0"
TMPFILES_UPLOAD = "https://tmpfiles.org/api/v1/upload"


class InstagramClient:
    def __init__(self, access_token=None):
        load_dotenv()
        self.token = access_token or os.environ["INSTAGRAM_ACCESS_TOKEN"]

    def _get(self, path, **params):
        params["access_token"] = self.token
        r = requests.get(f"{GRAPH_BASE}/{path}", params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path, **data):
        data["access_token"] = self.token
        r = requests.post(f"{GRAPH_BASE}/{path}", data=data)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _host_file(self, path: str) -> str:
        """Upload a local file to tmpfiles.org and return a direct-download URL."""
        with open(path, "rb") as f:
            r = requests.post(TMPFILES_UPLOAD, files={"file": f})
            r.raise_for_status()
        url = r.json()["data"]["url"]
        return url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1).replace("http://", "https://")

    def _create_container(self, media_type: str, caption: str = "",
                          image_url: str = "", video_url: str = "",
                          is_carousel_item: bool = False) -> str:
        """Create a media container on the Instagram API. Returns the container ID."""
        params = {"media_type": media_type}
        if image_url:
            params["image_url"] = image_url
        if video_url:
            params["video_url"] = video_url
        if caption and not is_carousel_item:
            params["caption"] = caption
        if is_carousel_item:
            params["is_carousel_item"] = True
        resp = self._post("me/media", **params)
        return resp["id"]

    # ------------------------------------------------------------------ #
    #  Publishing                                                          #
    # ------------------------------------------------------------------ #

    def wait_until_ready(self, container_id: str, timeout: int = 120, interval: int = 5) -> bool:
        """Poll container status until FINISHED or timeout. Returns True if ready."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.container_status(container_id)
            code = status.get("status_code")
            if code == "FINISHED":
                return True
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Container {container_id} failed: {status}")
            time.sleep(interval)
        return False

    def publish(self, container_id: str) -> str:
        """Publish a ready container. Returns the new media ID."""
        resp = self._post("me/media_publish", creation_id=container_id)
        return resp["id"]

    # ------------------------------------------------------------------ #
    #  Posting from local files                                            #
    # ------------------------------------------------------------------ #

    def post_photo(self, path: str, caption: str = "") -> str:
        """Post a photo from a local file. Returns the media ID."""
        url = self._host_file(path)
        container_id = self._create_container("IMAGE", caption=caption, image_url=url)
        self.wait_until_ready(container_id)
        return self.publish(container_id)

    def post_reel(self, path: str, caption: str = "") -> str:
        """Post a Reel from a local video file. Returns the media ID."""
        url = self._host_file(path)
        container_id = self._create_container("REELS", caption=caption, video_url=url)
        self.wait_until_ready(container_id)
        return self.publish(container_id)

    def post_carousel(self, items: list[dict], caption: str = "") -> str:
        """
        Post a carousel from local files.
        items: list of dicts with 'image_path' or 'video_path' keys.
        Example: [{"image_path": "/tmp/a.jpg"}, {"image_path": "/tmp/b.jpg"}]
        """
        children = []
        for item in items:
            if "image_path" in item:
                url = self._host_file(item["image_path"])
                child_id = self._create_container("IMAGE", image_url=url, is_carousel_item=True)
            elif "video_path" in item:
                url = self._host_file(item["video_path"])
                child_id = self._create_container("VIDEO", video_url=url, is_carousel_item=True)
            else:
                raise ValueError(f"Each item needs 'image_path' or 'video_path': {item}")
            children.append(child_id)

        for child_id in children:
            self.wait_until_ready(child_id)

        container_id = self._post(
            "me/media",
            media_type="CAROUSEL",
            children=",".join(children),
            caption=caption,
        )["id"]
        return self.publish(container_id)

    # ------------------------------------------------------------------ #
    #  Inspection                                                          #
    # ------------------------------------------------------------------ #

    def container_status(self, container_id: str) -> dict:
        """Returns status_code and any error info for a media container."""
        return self._get(container_id, fields="status_code,status")

    def get_media(self, limit: int = 10) -> list[dict]:
        """Returns recent posts (id, caption, media_type, timestamp)."""
        resp = self._get(
            "me/media",
            fields="id,caption,media_type,timestamp,permalink",
            limit=limit,
        )
        return resp.get("data", [])

    def get_media_info(self, media_id: str) -> dict:
        """Returns full info for a single media object."""
        return self._get(
            media_id,
            fields="id,caption,media_type,timestamp,permalink,like_count,comments_count",
        )
