"""读取 config.toml，并集中定义仓库里各个目录的位置。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.version_info < (3, 11):  # tomllib 从 3.11 起进入标准库
    raise SystemExit("drama-radar 需要 Python 3.11 及以上版本，当前是 %d.%d。" % sys.version_info[:2])

import tomllib

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Paths:
    root: Path
    # 可选覆盖（config.local.toml 的 [paths] 段）：把产生的数据放到仓库之外的文件夹。
    # 不设置时保持原样：data/、reports/、_site/ 都在仓库根目录下。
    data_dir: Optional[Path] = None
    reports_dir: Optional[Path] = None
    site_dir: Optional[Path] = None

    @property
    def data(self) -> Path:
        return self.data_dir or (self.root / "data")

    def snapshots(self, source: str) -> Path:
        return self.data / "snapshots" / source

    def catalog(self, source: str) -> Path:
        return self.data / "catalog" / f"{source}.json"

    def state(self, source: str) -> Path:
        return self.data / "state" / source

    @property
    def reports(self) -> Path:
        return self.reports_dir or (self.root / "reports")

    @property
    def web(self) -> Path:
        return self.root / "web"

    @property
    def site(self) -> Path:
        return self.site_dir or (self.root / "_site")


@dataclass
class Config:
    raw: Dict[str, Any]
    paths: Paths

    @property
    def general(self) -> Dict[str, Any]:
        return self.raw.get("general", {})

    @property
    def analysis(self) -> Dict[str, Any]:
        return self.raw.get("analysis", {})

    @property
    def reporters(self) -> Dict[str, Dict[str, Any]]:
        return self.raw.get("reporters", {})

    def source(self, source_id: str) -> Dict[str, Any]:
        return self.raw.get("sources", {}).get(source_id, {})

    def enabled_sources(self) -> List[str]:
        return [k for k, v in self.raw.get("sources", {}).items() if v.get("enabled", True)]

    @property
    def tz_offset(self) -> int:
        return int(self.general.get("timezone_offset_hours", 8))

    @property
    def cutoff_hour(self) -> int:
        return int(self.general.get("batch_cutoff_hour", 9))


def _merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """浅合并按节深合并：config.local.toml 的同名节覆盖 config.toml。"""
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Optional[Path] = None, root: Optional[Path] = None) -> Config:
    root = Path(root) if root else ROOT
    path = Path(path) if path else root / "config.toml"
    raw: Dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    # 本地覆盖层：config.local.toml 不提交（见 .gitignore），用来把数据放到仓库之外的文件夹，
    # 云端 GitHub Actions 读不到它，行为保持原样。
    local_path = root / "config.local.toml"
    if local_path.exists():
        with local_path.open("rb") as fh:
            raw = _merge(raw, tomllib.load(fh))
    overrides = raw.get("paths", {}) or {}

    def _resolve(key: str) -> Optional[Path]:
        if key not in overrides:
            return None
        p = Path(overrides[key])
        return p if p.is_absolute() else (root / p)

    return Config(
        raw=raw,
        paths=Paths(
            root,
            data_dir=_resolve("data_dir"),
            reports_dir=_resolve("reports_dir"),
            site_dir=_resolve("site_dir"),
        ),
    )
