# Hashstore Compaction — Log Mining Analysis

## Overview

Storj storage nodes perform periodic hashstore compaction (~every 12 hours) for each
satellite × store combination. These compaction events emit a structured sequence of
INFO-level log entries under the `hashstore` area that contain rich operational data
currently being discarded by the parser.

This document defines what information can be extracted and what statistics/views can
be presented to the user.

---

## Log Event Sequence

Each compaction cycle produces this ordered sequence (per satellite × store):

| #   | Message                                      | Occurs       | Key Role                                   |
| --- | -------------------------------------------- | ------------ | ------------------------------------------ |
| 1   | `beginning compaction`                       | Once         | Snapshot BEFORE compaction                 |
| 2   | `compact once started`                       | 1+ per cycle | Pass start marker                          |
| 3   | `including log due to no rewrite candidates` | 0-1 per pass | Edge case: forced inclusion                |
| 4   | `compaction computed details`                | 1 per pass   | Planning phase results                     |
| 5   | `records rewritten`                          | 1 per pass   | Data I/O phase results                     |
| 6   | `hashtbl rewritten`                          | 1 per pass   | Detailed deltas for this pass              |
| 7   | `compact once finished`                      | 1 per pass   | Pass completion + `completed` flag         |
| 8   | `finished compaction`                        | Once         | Snapshot AFTER compaction + total duration |

A cycle has **multiple passes** when `completed: false` triggers a retry (observed on
larger stores or when modifications are detected mid-cycle).

---

## Identification Dimensions

Every compaction event is scoped by:

| Dimension     | Source                             | Example                                               |
| ------------- | ---------------------------------- | ----------------------------------------------------- |
| **Node**      | Log source (TCP connection / file) | "Node1", "Node3"                                      |
| **Satellite** | `satellite` field (NodeID)         | `12L9ZFwhzVpuEKMUNUqkaTLGzwY9G24tbiigLiXpmZWKwmcNDDs` |
| **Store**     | `store` field                      | `s0`, `s1`                                            |

---

## Extractable Metrics

### A. Storage Composition (from `beginning`/`finished` → `stats.Table`)

| Metric                   | JSON Path         | Unit              | Description                                 |
| ------------------------ | ----------------- | ----------------- | ------------------------------------------- |
| Live data size           | `Table.LenSet`    | bytes (human str) | Actual useful piece data                    |
| Live record count        | `Table.NumSet`    | count             | Number of live pieces stored                |
| Average piece size       | `Table.AvgSet`    | bytes (float)     | Mean piece size — workload characterization |
| Trash data size          | `Table.LenTrash`  | bytes             | Deleted but not yet reclaimed               |
| Trash record count       | `Table.NumTrash`  | count             | Pieces pending reclamation                  |
| Average trash piece size | `Table.AvgTrash`  | bytes             | —                                           |
| TTL data size            | `Table.LenTTL`    | bytes             | Temporary/expiring data                     |
| TTL record count         | `Table.NumTTL`    | count             | —                                           |
| Hash table load factor   | `Table.Load`      | float 0-1         | Fullness of hash table (resize at ~0.7)     |
| Hash table size          | `Table.TableSize` | bytes             | Memory/disk overhead of table               |
| Hash table slots         | `Table.NumSlots`  | count             | Capacity of hash table                      |
| Table creation day       | `Table.Created`   | day number        | When current table was created              |

### B. Store-Level Stats (from `beginning`/`finished` → `stats`)

| Metric                    | JSON Path         | Unit       | Description                          |
| ------------------------- | ----------------- | ---------- | ------------------------------------ |
| Total log size            | `LenLogs`         | bytes      | Raw on-disk footprint (logs + data)  |
| Log file count            | `NumLogs`         | count      | Fragmentation indicator              |
| TTL log size              | `LenLogsTTL`      | bytes      | —                                    |
| TTL log count             | `NumLogsTTL`      | count      | —                                    |
| Set percentage            | `SetPercent`      | float 0-1  | Fraction that is live data           |
| Trash percentage          | `TrashPercent`    | float 0-1  | Fraction that is trash               |
| TTL percentage            | `TTLPercent`      | float 0-1  | Fraction that is TTL                 |
| Data reclaimable          | `DataReclaimable` | bytes      | Space that could be freed next cycle |
| Free space required       | `FreeRequired`    | bytes      | Minimum free disk for compaction     |
| Total compactions         | `Compactions`     | count      | Lifetime compaction counter          |
| Cumulative data rewritten | `DataRewritten`   | bytes      | Total I/O over store lifetime        |
| Cumulative data reclaimed | `DataReclaimed`   | bytes      | Total space recovered lifetime       |
| Cumulative logs rewritten | `LogsRewritten`   | count      | —                                    |
| Last compaction day       | `LastCompact`     | day number | Schedule tracking                    |

### C. Per-Pass Performance (from `records rewritten` + `hashtbl rewritten`)

| Metric                   | Source Message      | JSON Path          | Description                                 |
| ------------------------ | ------------------- | ------------------ | ------------------------------------------- |
| Records rewritten count  | `records rewritten` | `records`          | Piece data physically moved                 |
| Bytes rewritten          | `records rewritten` | `bytes`            | I/O volume of data move                     |
| Rewrite duration         | `records rewritten` | `duration`         | Time for data movement phase                |
| Hashtbl rewrite duration | `hashtbl rewritten` | `duration`         | Time for table rebuild                      |
| Total records after      | `hashtbl rewritten` | `total_records`    | Store-wide record count                     |
| Total bytes after        | `hashtbl rewritten` | `total_bytes`      | Store-wide data size                        |
| Trashed records          | `hashtbl rewritten` | `trashed_records`  | Records moved to trash this pass            |
| Trashed bytes            | `hashtbl rewritten` | `trashed_bytes`    | Data moved to trash                         |
| Restored records         | `hashtbl rewritten` | `restored_records` | Recovered from trash                        |
| Restored bytes           | `hashtbl rewritten` | `restored_bytes`   | —                                           |
| Expired records          | `hashtbl rewritten` | `expired_records`  | TTL-expired pieces removed                  |
| Expired bytes            | `hashtbl rewritten` | `expired_bytes`    | —                                           |
| Reclaimed log count      | `hashtbl rewritten` | `reclaimed_logs`   | Log files freed                             |
| Reclaimed bytes          | `hashtbl rewritten` | `reclaimed_bytes`  | Disk space actually freed                   |
| Reclaim ratio            | `hashtbl rewritten` | `reclaim_ratio`    | Efficiency: reclaimed/rewritten (>1 = good) |

### D. Cycle-Level Metrics (from `compact once finished` + `finished compaction`)

| Metric               | Source                            | Description                    |
| -------------------- | --------------------------------- | ------------------------------ |
| Pass duration        | `compact once finished.duration`  | Time for one compaction pass   |
| Pass completed flag  | `compact once finished.completed` | false = another pass needed    |
| Total cycle duration | `finished compaction.duration`    | Wall-clock time for full cycle |
| Number of passes     | Count of `compact once started`   | Complexity/workload indicator  |

### E. Planning Phase (from `compaction computed details`)

| Metric                 | JSON Path       | Description                            |
| ---------------------- | --------------- | -------------------------------------- |
| Current set count      | `nset`          | Live records at planning time          |
| Existing record count  | `nexist`        | Total records including pending        |
| Modifications detected | `modifications` | Whether new writes occurred since last |
| Candidate log IDs      | `candidates`    | Logs considered for rewrite            |
| Rewrite target IDs     | `rewrite`       | Logs selected for rewrite              |
| Planning duration      | `duration`      | Time to compute rewrite plan           |

---

## Derived Statistics & Visualizations

### Dashboard Panels

1. **Storage Breakdown** (stacked area chart over time)
   - Live (LenSet) vs Trash (LenTrash) vs TTL (LenTTL) per satellite×store
   - Shows how storage composition evolves

2. **Compaction Duration Trend** (line chart)
   - Total cycle duration over time per satellite×store
   - Alert if duration trends upward (disk degradation / growth)

3. **Reclamation Effectiveness** (bar chart per compaction)
   - Bytes reclaimed vs bytes rewritten per cycle
   - Reclaim ratio trend (should stay stable or improve)

4. **Trash Accumulation Rate** (line chart)
   - TrashPercent between compactions
   - Delta of NumTrash between cycles → trash creation rate

5. **Hash Table Health** (gauge per satellite×store)
   - Load factor with thresholds: green <0.5, yellow 0.5-0.7, red >0.7
   - Alert when approaching resize threshold

6. **Disk Space Projection** (line + forecast)
   - LenLogs growth trend
   - DataReclaimable as "potential savings"
   - FreeRequired as "minimum headroom"

7. **Average Piece Size Trend** (line chart)
   - AvgSet over time per satellite
   - Detects workload shifts (smaller pieces = more overhead)

8. **Compaction Schedule** (heatmap / timeline)
   - When compactions fire per satellite×store
   - Visualize the ~12h cadence, detect scheduling issues

9. **Multi-Pass Indicator** (table/badge)
   - Which satellite×store combinations need multiple passes
   - Correlates with store size and modification rate

10. **Compaction Throughput** (derived)
    - MB/s rewrite speed = bytes_rewritten / rewrite_duration
    - Indicates disk I/O performance under compaction load

### Alerts / Anomaly Detection

| Condition                | Threshold                        | Meaning                                               |
| ------------------------ | -------------------------------- | ----------------------------------------------------- |
| Load factor > 0.7        | `Table.Load > 0.7`               | Hash table resize imminent                            |
| Duration spike           | >2× rolling average              | Disk issues or unexpected growth                      |
| Reclaimable growing      | DataReclaimable increasing trend | Compaction not keeping up                             |
| Reclaim ratio < 0.3      | Per-pass                         | Inefficient compaction (lots of rewrite, little gain) |
| FreeRequired > available | Needs external disk check        | Node may stall                                        |
| Compaction gap > 24h     | `Today - LastCompact > 1`        | Missed compaction cycle                               |

---

## Observed Data Ranges (from 2 nodes, 4 satellites)

| Dimension             | Minimum  | Maximum   |
| --------------------- | -------- | --------- |
| Store size (LenLogs)  | 2.4 GiB  | 2.2 TiB   |
| Record count (NumSet) | 1,165    | 8,801,092 |
| Avg piece size        | 165 KiB  | 2.3 MiB   |
| Hash table load       | 0.07     | 0.48      |
| TableSize             | 1.0 MiB  | 2.0 GiB   |
| FreeRequired          | 12.0 MiB | 24.0 GiB  |
| Compaction duration   | 118ms    | 4m31s     |
| DataReclaimable       | 0 B      | 293.5 GiB |
| Passes per cycle      | 1        | 2         |
| Reclaim ratio         | 0.002    | +Inf      |

---

## Additional Log Types (non-compaction, same area)

| Area         | Action                                                    | Relevance                                                                         |
| ------------ | --------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `piecestore` | `download failed` with `"hashstore: file does not exist"` | Correlates with deleted/compacted pieces — could track as "compaction collisions" |

---

## Size Parsing Notes

The logs use human-readable size strings that need parsing:

- Formats: `"0 B"`, `"8.3 KiB"`, `"549.4 MiB"`, `"3.4 GiB"`, `"0.8 TiB"`
- Binary units (KiB/MiB/GiB/TiB = 1024-based)
- Some values use decimal units: `"273.27 MB"` (observed once — may be a bug in node code)
- Duration formats: `"185.512939ms"`, `"25.738324484s"`, `"1m42.132875157s"`, `"2m11.348304508s"`
- Microseconds: `"413.138µs"`
- Special values: `"+Inf"` for reclaim_ratio when rewritten_bytes = 0
- `Table.AvgSet`, `Table.AvgTrash`, `Table.AvgTTL` are raw floats (bytes)
- Day numbers (e.g. `20600`, `20601`) — days since Unix epoch (2026-05-27 = day 20600)

---

## Frequency & Volume Estimate

- ~12h between compactions per satellite×store
- 4 satellites × 2 stores × 2 events/day = ~16 compaction cycles/day/node
- Each cycle = 1 DB row (if stored as summary) — negligible storage
- With 3 nodes: ~48 rows/day → ~17,500 rows/year

---

## Open Design Questions

1. **Granularity**: Store one row per full cycle (recommended) or one per pass?
   - Recommendation: One row per cycle with `passes` count; multi-pass data aggregated
2. **Store dimension**: Keep `store` (s0/s1) as separate column or aggregate per satellite?
   - Recommendation: Keep separate — stores have very different sizes
3. **Before/after snapshots**: Store both, or just the "finished" snapshot + deltas?
   - Recommendation: Store "finished" snapshot + computed deltas (before can be derived from previous row)
4. **Retention**: How long to keep history?
   - Recommendation: Same as other tables (configurable, default 90 days)
5. **Correlation**: Track "hashstore: file does not exist" errors alongside compaction?
   - Recommendation: Yes, as a separate counter/metric
