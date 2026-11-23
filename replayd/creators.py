"""Simple descriptive creator insights. Never claimed as causal predictions."""
from __future__ import annotations

import pandas as pd


def compare_content_types(df: pd.DataFrame, min_posts: int = 3) -> pd.DataFrame:
    """Group previously analyzed posts; minimum sample suppresses thin claims.

    `shares_per_1000_views` is a *per-post* ratio; median is used to reduce
    influence of outliers. This is not a platform-defined engagement metric.
    """
    if "content_type" not in df:
        return pd.DataFrame(columns=["content_type", "posts", "median_shares_per_1000_views", "median_interactions_per_100_views"])
    clean = df.copy()
    clean["content_type"] = clean["content_type"].fillna("").astype(str).str.strip()
    clean = clean[clean["content_type"] != ""]
    if clean.empty:
        return pd.DataFrame(columns=["content_type", "posts", "median_shares_per_1000_views", "median_interactions_per_100_views"])
    grouped = clean.groupby("content_type", as_index=False).agg(
        posts=("clip_id", "size"),
        median_shares_per_1000_views=("shares_per_1000_views", "median"),
        median_interactions_per_100_views=("interactions_per_100_views", "median"),
    )
    return grouped[grouped["posts"] >= min_posts].sort_values(
        ["median_shares_per_1000_views", "posts"], ascending=[False, False]
    ).reset_index(drop=True)
