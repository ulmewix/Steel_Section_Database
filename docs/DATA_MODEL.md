# Data model

`data/` holds the only hand-edited engineering data: the **primary geometry** of each profile and the metadata needed to
interpret it. Derived properties (A, I, W, Wpl, i, mass, …) are never stored here; they are computed by
`section_properties` and written to `generated/`.

## Files

One profile series = one table + one metadata file in a folder per family (`data/ipe/`, `data/shs/`, …):

| File | Content |
|---|---|
| `<ID>.csv` | table of primary geometry, one row per profile — rendered as a table on GitHub |
| `<ID>.toml` | series metadata and comments |

The file names must equal the series `id` (e.g. `data/ipe/IPE.csv`, `data/ipe/IPE.toml`, `data/shs/SHS-HF.csv`,
`data/shs/SHS-CF.toml`). Hot-finished and cold-formed hollow sections of one family share the folder but are separate
series.

## CSV rules (enforced by `python -m tools.cli fmt --check` and `check`)

- UTF-8 without BOM, LF line endings, final newline; separator `,`; decimal point `.`.
- Numbers in plain, shortest notation: no exponent, no trailing zeros (`19`, `5.2`, `8.75`).
  Values are read as exact decimals and converted to floating point once, when geometry is built.
- Header = the shape's columns in canonical order (see `schema/rows.schema.json`). An empty cell means "not set".
- Rows sorted by the shape's key (`I`, `I_TAPERED`, `U`, `U_TAPERED`: h; `SHS`: b, t; `RHS`: h, b, t; `CHS`: D, t;
  `L_EQ`: b, t; `L`: h, b, t; `FLAT`: b, t; then designation); designations unique.
- Editing in a spreadsheet with a Czech locale may silently switch to `;` and decimal commas — `fmt --check` catches that.

## Series metadata (TOML)

| Key | Meaning |
|---|---|
| `schema_version` | `1` — version of this metadata format (`schema/series.schema.json`), read only by this repository's tools; independent of the web JSON contract version ([CONVENTIONS.md](CONVENTIONS.md#web-json-contract)) |
| `id` | series id, e.g. `IPE`, `SHS-HF`, `RHS-CF`, `CHS-HF`, `L-EQ` |
| `title` | human-readable name |
| `shape` | selects the columns and the geometry builder (`I`, `I_TAPERED`, `U`, `U_TAPERED`, `SHS`, `RHS`, `CHS`, `L_EQ`, `L`, `FLAT`) |
| `standard` | specification that defines the series — see below |
| `process` | `hot_rolled` / `hot_finished` / `cold_formed` — part of the profile identity |
| `corner_radii` | shapes `SHS`, `RHS` only (required there): rule of the corner radii, `EN10210-2` or `EN10219-2` (see below) |
| `[corner_radii_overrides]` | shapes `SHS`, `RHS` only, optional: `"<designation>" = "<reason>"` for rows whose explicit ro/ri override the rule |
| `[designation]` | `pattern` (e.g. `"IPE {h}"`) and `aliases` |
| `[conventions]` | optional: convention-dependent properties this series publishes (It, Wt, Iw, ym), e.g. `It = { method = "IT_ROLLED_I_FILLET_V1" }`. Absent = `unsupported` (null). The method must be implemented for the shape — see [CONVENTIONS.md](CONVENTIONS.md) |

### `standard`

`standard` names the specification that **defines the series** (designation system, nominal dimensions, calculation
rules), e.g. `EN 10365:2017`, as a declaration of membership. The edition is the one whose rules and tables the data
follow (hollow sections: the 2006 editions). A series that is a mixed catalogue range says so instead of naming one
standard (angles: "Mixed range: EN 10056-1:1998 (…, 24 of 42 sizes); other sizes …"); a series without a defining
standard states what is assumed (flat bars: "Assumed: hot-rolled flats of EN 10058 (sizes not checked)").

`standard` does **not** mean that the stored values were checked against that standard or edition, nor that every size
of the series is in the standard's tables. The dimensions have not yet been checked row by row against licensed copies
of the standards' tables.

Standards are cited by designation, edition and clause only (EN 10365, EN 10210-2, EN 10219-2, EN 10024, EN 10056-1,
EN 10058, EN 1993-1-1, DIN 1025, DIN 1026, DIN 1028, DIN 1029); no normative text is reproduced.

## Designations

Canonical form: prefix, one space, dimensions in shortest notation (`IPE 200`). The designation is deliberately redundant
with the dimensions and acts as a checksum: `check` verifies it against the `pattern` (`{h}` is replaced by the row's
`h`; `{n}` accepts any number).

## Axes and units

- Input lengths in mm, slopes in % (100·tan α). Frame (y, z): y horizontal, z vertical (EN 1993-1-1); y-y is the major
  axis of an I-section or a channel (parallel to the flanges), z-z the minor axis (along the web).
- Local frame of each shape: doubly symmetric shapes (`I`, `I_TAPERED`, `SHS`, `RHS`, `CHS`, `FLAT`) have their centre at
  the origin; channels (`U`, `U_TAPERED`) have the back of the web on the z axis (y = 0), the flanges pointing toward +y,
  z = 0 at mid-depth; angles (`L_EQ`, `L`) have the heel at the origin, the leg h along +z and the leg b along +y; flat bars
  (`FLAT`) stand on edge: the width b along z (as the depth h of an I section) and the thickness t along y, so that y-y is
  their strong axis. The frame follows from the meaning of the parameters, never from the order of the columns of a file.
- Every shape except the angles is symmetric about its y axis (it declares `SYMMETRIC_ABOUT_Y`): Iyz = 0 and y, z are the
  principal axes (published exactly: Iyz = 0, alpha = 0 — 90° if Iz > Iy, which no current row has). Angles have Iyz < 0
  and inclined principal axes u, v at the angle alpha from +y ([CONVENTIONS.md](CONVENTIONS.md#frame-and-sign-conventions)).
- The published `ys` / `zs` are the distances of the centroid from the extreme fibre with the smallest y / z (channels: ys
  from the back of the web; angles: ys from the back of leg h, zs from the back of leg b — the catalogue ys, zs);
  `Wel_z_left` / `Wel_z_right` and `Wel_y_bottom` / `Wel_y_top` are the elastic moduli at the fibres with the smallest /
  largest y and z (channels: back of the web / flange tips; angles: the tips of leg b and leg h are `Wel_z_right` and
  `Wel_y_top`, the catalogue Wel,z and Wel,y).
- Output units: see [CONVENTIONS.md](CONVENTIONS.md#output-units-and-rounding).

## Shapes

### `I` — doubly symmetric I/H section, parallel flanges

```
          |<------------ b ------------>|
          +-----------------------------+  ---
          |                             |   | tf
          +-----------.     .-----------+  ---      z
                       \r  /                         ^
                       |    |                        |
                       |    |<- tw                   +--> y
             h         |    |
                       |    |                y-y: major axis (parallel to the flanges)
                       /r   \                z-z: minor axis (along the web)
          +-----------'     '-----------+
          |                             |
          +-----------------------------+
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | e.g. `IPE 200` |
| `h` | mm | overall depth |
| `b` | mm | flange width |
| `tw` | mm | web thickness |
| `tf` | mm | flange thickness |
| `r` | mm | root radius (web–flange fillet, four fillets) |

Flange tips are square. Feasibility: all dimensions > 0 (r ≥ 0), flange flat (b − tw)/2 − r > 0, web flat h − 2tf − 2r > 0.
Infeasible geometry is rejected, never silently corrected.

Never stored (derivable): d, hi, hf, mass, A, I, W, Wpl, i, It, Iw, surface, nominal size, symmetry flags.

### `I_TAPERED` — doubly symmetric I section with sloped flanges (IPN)

```
          |<------------------ b ------------------>|
          +-----------------------------------------+  ---
          |                                         |   |
          +-._ r2   tf at x_tf from the tip  r2 _.-+   |    inner flange faces sloped:
               '-._                         _.-'        |    slope_pct = 100·tan α
                    '-.__ r1        r1 __.-'            |
                         |          |                   h
                         |<-- tw -->|                   |
                         |          |                   |
                     __.-' r1    r1 '-.__               |
                _.-'                        '-._        |
          +-'` r2                             r2 `'-+   |
          |                                         |   |
          +-----------------------------------------+  ---
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | e.g. `IPN 200` |
| `h` | mm | overall depth |
| `b` | mm | flange width |
| `tw` | mm | web thickness |
| `tf` | mm | flange thickness, measured at the distance `x_tf` from the flange tip |
| `r1` | mm | root radius (web–flange fillet, four fillets) |
| `r2` | mm | toe radius (inner edge of the four flange tips) |
| `slope_pct` | % | slope of the inner flange faces, 100·tan α (IPN: 14) |
| `x_tf` | mm | distance of the tf measuring point from the flange tip (IPN: b/4, i.e. b/4 from the mid-width of the flange) |

Each of the four flange outstands runs from the web face (y = tw/2) to the tip (y = b/2). Its inner face is a straight line
with slope s = slope_pct/100 and thickness t(y) = tf + (b/2 − x_tf − y)·s (thicker toward the web); the root fillet r1 and
the toe arc r2 are tangent to the two straight faces they join (each turns by 90° − α); the outer corners are sharp.
Shape-independent algebra: `section_properties/shapes/channel.py`. Feasibility (exact decimals): h, b, tw, tf > 0;
r1, r2, slope_pct ≥ 0; the outstand (b − tw)/2 > 0; 0 < x_tf < (b − tw)/2 for a sloped flange; the straight web between
the root fillets, the straight inner flange face between root fillet and toe arc, and the straight flange tip must have
positive length. Infeasible geometry is rejected, never corrected.

The data carry the exact value of the rule for `x_tf` (IPN 260: 113/4 = 28.25 mm), not a value rounded to 0.1 mm. The radii
are the printed dimensions (see [Series notes](#channels-and-taper-flange-i-sections-upn-upe-ipn)); no rule is imposed on
them.

### `U` — channel with parallel flanges (UPE)

```
     |<------ b ------>|
     +-----------------+  ---
     |                 |   | tf              z
     |    .------------+  ---                ^
     |   / r                                 |
     |  |                                    +--> y   (back of the web at y = 0)
  h  |  |<- tw
     |  |
     |   \ r
     |    `------------+
     |                 |
     +-----------------+
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | e.g. `UPE 200` |
| `h` | mm | overall depth |
| `b` | mm | flange width, from the back of the web to the flange tip |
| `tw` | mm | web thickness |
| `tf` | mm | flange thickness |
| `r` | mm | root radius (two fillets) |

Square flange tips and sharp outer corners. It is the channel of `U_TAPERED` with slope 0 and r2 = 0. Feasibility:
h, b, tw, tf > 0, r ≥ 0; straight web h − 2·tf − 2·r > 0; straight inner flange face b − tw − r > 0.

### `U_TAPERED` — channel with sloped flanges (UPN)

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | e.g. `UPN 200` |
| `h` | mm | overall depth |
| `b` | mm | flange width, from the back of the web to the flange tip |
| `tw` | mm | web thickness |
| `tf` | mm | flange thickness, measured at the distance `x_tf` from the flange tip |
| `r1` | mm | root radius |
| `r2` | mm | toe radius |
| `slope_pct` | % | slope of the inner flange faces, 100·tan α (UPN: 8 for h ≤ 300, 5 for h > 300) |
| `x_tf` | mm | distance of the tf measuring point from the flange tip: UPN h ≤ 300: b/2 (the middle of b); h > 300: (b − tw)/2 (the middle of the free flange length, i.e. (b − tw)/2 from the inner face of the web) |

The flange outstand runs from the inner face of the web (y = tw) to the tip (y = b); its inner face has the thickness
t(y) = tf + (b − x_tf − y)·s, with root fillet and toe arc as for `I_TAPERED`. Feasibility (exact decimals): h, b, tw,
tf > 0; r1, r2, slope_pct ≥ 0; the outstand b − tw > 0; 0 < x_tf < b − tw for a sloped flange; the straight web between
the root fillets, the straight inner flange face and the straight flange tip must have positive length.

Measuring x_tf from the tip gives both rules of the standard one meaning. Applying tf at b/2 also for UPN 320 … 400 would
place it tw/2 nearer the tip, thin each flange by s·tw/2 and lose 0.74 … 0.79 % of the area (UPN 320: 7577.33 → 7517.13 mm²,
Iy −1.1 %; pinned by `tests/test_shape_channel.py`). The data carry the exact value of the rule
(UPN 380: (102 − 13.5)/2 = 44.25 mm).

Never stored for U, U_TAPERED, I_TAPERED (derivable): d, hi, mass, A, I, W, Wpl, i, ys, It, Iw, ym, surface.

### `SHS`, `RHS` — square / rectangular hollow section

```
          |<------------- b ------------->|
          .-------------------------------.   ---
         /  ro                         ro  \   |
        |    .-------------------------.    |  |
        |   / ri                     ri \   |  |          z
        |  |                             |  |  |          ^
        |  |                             |  |  h          |
        |  |                             |<-|--|-- t      +--> y
        |   \ ri                     ri /   |  |
        |    '-------------------------'    |  |    y-y: major axis (h ≥ b)
         \  ro                         ro  /   |
          '-------------------------------'   ---
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | `RHS 200x100x8` (h × b × t), `SHS 100x100x5` (b × b × t) |
| `h` | mm | overall depth (RHS only; SHS: h = b) |
| `b` | mm | overall width |
| `t` | mm | wall thickness (all four walls) |
| `ro` | mm | outer corner radius — **empty = series rule** |
| `ri` | mm | inner corner radius — **empty = series rule** |

Corner radii are not stored: the series names its rule in `corner_radii` and the engine evaluates it in exact decimal
arithmetic from `t` (1.5 × 6.3 = 9.45 mm, never rounded):

| `corner_radii` | Process | t | ro | ri |
|---|---|---|---|---|
| `EN10210-2` | hot finished | any | 1.5·t | 1.0·t |
| `EN10219-2` | cold formed | t ≤ 6 mm | 2.0·t | 1.0·t |
| `EN10219-2` | cold formed | 6 < t ≤ 10 mm | 2.5·t | 1.5·t |
| `EN10219-2` | cold formed | t > 10 mm | 3.0·t | 2.0·t |

These are the calculation radii of EN 10210-2:2006 A.3 and EN 10219-2:2006 B.3 (the thresholds are ≤, not <; clause A.3 of
the 2019 editions keeps them). The real corner is a tolerance band (EN 10219-2 Table 3: 1.6–2.4 T, 2.0–3.0 T, 2.4–3.6 T;
the calculation radius is the middle of each band); neither standard specifies the internal corner, so ri is purely a
calculation convention. Hot-finished corners (ro = 1.5·t, ri = t) are not concentric: the inner corner centre lies 0.5·t
further inside, so the corner is thicker than t.

Filled `ro` and `ri` cells (always both) override the rule for that row; each override must be listed in
`[corner_radii_overrides]` with a short reason (checked by `tools.cli check`). There is none in the current data. The
resolved radii — rule or override — are echoed in the web JSON geometry and in `generated/properties/<ID>.csv` (column
`corner_radii` names the rule, or the reason of an override); the web JSON of the series carries `"corner_radii"`.

Hot-finished and cold-formed profiles share designations but not radii, so the process is part of the identity: separate
series (`SHS-HF`, `SHS-CF`, `RHS-HF`, `RHS-CF`) and web ids `<series>/<designation>`
(`SHS-HF/SHS 100x100x5` ≠ `SHS-CF/SHS 100x100x5`).

Feasibility (resolved radii, exact decimals): h, b, t > 0; ro, ri ≥ 0; RHS h ≥ b (y-y is the major axis; SHS h = b); a
hole: b − 2·t > 0 and h − 2·t > 0; outer flats b − 2·ro ≥ 0 and h − 2·ro ≥ 0; inner flats b − 2·t − 2·ri ≥ 0 and
h − 2·t − 2·ri ≥ 0 (a flat of exactly 0 is a semicircular end, e.g. hot-finished RHS 70x40x10); positive wall thickness in
the corner (smallest distance between the outer and inner corner arc, evaluated exactly: with d = ro − ri, d ≤ t or
d² > 2·(d − t)²). The corner-radius rule must belong to the series' process (`EN10210-2` ↔ `hot_finished`, `EN10219-2` ↔
`cold_formed`). `tools.cli check` and `build` evaluate these conditions on the exact decimals of every row
(`io.resolved_rows` raises `GeometryError`); infeasible geometry is rejected, never cut or corrected.

Never stored (derivable): d, hi, bi, radii of the rule, mass, A, I, W, Wpl, i, It, Wt, surface.

### `L_EQ`, `L` — hot-rolled angles (equal and unequal legs)

```
      z
      ^
      +--.           end of leg h: toe radius r2 at the inner edge, outer edge sharp
      |   \
      |   |
    h |   |<- t
      |   |
      |    \          root radius r1
      |     `-------.
      |              \  toe radius r2
      |              |  t
      +--------------+---> y      heel (sharp) at the origin
      |<---- b ----->|
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | `L 100x100x10` (`L_EQ`: b × b × t), `L 150x100x10` (`L`: h × b × t, the longer leg first) |
| `h` | mm | shape `L` only: the longer leg, along z (h ≥ b); `L_EQ`: h = b |
| `b` | mm | leg along y (`L_EQ`: both legs) |
| `t` | mm | thickness of both legs |
| `r1` | mm | root radius (between the inner faces of the legs) |
| `r2` | mm | toe radius at the inner edge of each leg end |

The root radius is tangent to both inner faces, each toe radius to the inner face and the end face of its leg; the heel and
the outer edges of the leg ends are sharp (the outline of EN 10056-1:1998 Figures 1 and 2). Area
A = t·(h + b − t) + (1 − π/4)·(r1² − 2·r2²) (the Note 1 formula of EN 10056-1:1998). EN 10056-1 computes with r2 = r1/2;
the data carry the printed radii and no rule is imposed on r2 (one row departs from r1/2, see
[Series notes](#angles-l-eq-l)). Feasibility (exact decimals): h, b, t > 0; r1, r2 ≥ 0; each leg longer than t; straight
inner faces h − t − r1 − r2 ≥ 0 and b − t − r1 − r2 ≥ 0; straight leg ends t − r2 ≥ 0; shape `L`: h ≥ b. A straight part of
exactly 0 is valid (root fillet and toe arc then meet tangentially, or the toe arc meets the outer face at a corner), a
negative one is rejected, never corrected. In the data every straight part is positive (smallest inner face 15.5 mm,
L 60x30x7; smallest leg end 1 mm, L 40x40x4). The heel radius r3 of the heaviest rolled angles (e.g. 250 and 300 mm legs)
is not modelled; such sizes would need a new shape parameter.

Never stored for L_EQ, L (derivable): mass, A, ys, zs, I, Iyz, principal values, alpha, W, Wpl, i, It, surface, nominal size.

### `CHS` — circular hollow section

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | `CHS 168.3x8` (D × t) |
| `D` | mm | outside diameter |
| `t` | mm | wall thickness |

Feasibility: D > 0, t > 0, D − 2·t > 0. The outline is two exact circles; the engine integrates the annulus in closed form
(no polygon). Hot-finished and cold-formed CHS are separate series (`CHS-HF`, `CHS-CF`) although their geometry does not
depend on the process.

### `FLAT` — flat bar

```
               z
               ^
          +----|----+  ---
          |    |    |   |
          |    |    |   |
          |    |    |   |
          |    +----|---|--> y      the bar stands on edge, centre at the origin
          |         |   b
          |         |   |
          |         |   |
          +---------+  ---
          |<-- t -->|

          y-y: the STRONG axis (Iy = t·b³/12), as for an I section: u = y, alpha = 0°
          z-z: the weak axis   (Iz = b·t³/12)
```

| Column | Unit | Meaning |
|---|---|---|
| `designation` | – | `FLAT 200x10` (b × t) |
| `b` | mm | width of the bar, along z (the bar stands on edge) |
| `t` | mm | thickness, along y |

A solid rectangle with four sharp corners. The canonical bar stands on edge: its width b lies along z, as the depth h of an I
section, and its thickness t along y — unlike the other shapes, whose width b lies along y. The principal axes are y and z
(Iyz = 0); for b > t — every row — y-y is the strong axis: alpha = 0°, Iu = Iy, Iv = Iz. A bar used lying flat is a later
choice of the orientation of use by the consuming application, not a second set of data. The frame fixes the meaning of the
published Iy, Iz, Wel, Wpl and i of the flat bars. Feasibility: b > 0, t > 0, nothing else (a square or a bar thicker than
wide is a valid rectangle; the data have b > t). Every property is the closed form of the rectangle (A = b·t,
Iy = t·b³/12, Wpl,y = t·b²/4, …; checked against `tests/flat_reference.py`). It, Wt, Iw and ym are unsupported
([CONVENTIONS.md](CONVENTIONS.md#unsupported-properties)).

Never stored (derivable): mass, A, I, W, Wpl, i, It, surface.

## Series notes

Scope rules and non-obvious values of the data. A change of any of them is a change of the data and needs the same care as
any other edit of `data/` (see README, "How to add or edit a profile").

### I sections (IPE, HEA, HEB, HEM)

- `standard` = `EN 10365:2017`. EN 10365:2017 has been superseded by EN 10365:2026; whether any dimension changed has not
  been checked, so the field stays `EN 10365:2017` until the series is checked against an edition.
- HEM is the HE M range of EN 10365. The section 320 × 305 × 16 × 29 (r 27), sometimes listed as "HEM 320/305" (DIN 1025-4
  tradition), belongs to the HE C series of EN 10365 (HE 300 C) and is not part of HEM; it could become part of its own series.

### Hollow sections (SHS, RHS, CHS)

- The process is part of the identity: hot finished (EN 10210-2, `hot_finished`) and cold formed (EN 10219-2, `cold_formed`)
  are separate series. Designations `SHS {b}x{b}x{t}`, `RHS {h}x{b}x{t}` (h ≥ b), `CHS {D}x{t}`.
- `standard` names the 2006 editions (EN 10210-2:2006, EN 10219-2:2006): the corner radii and the It/Wt formulas of the
  rectangular sections (A.3 / B.3), the It/Wt of CHS (A.2 / B.2) and the CHS diameter list (Tables B.1 / C.1) are those of the
  2006 editions. Clause A.3 of the 2019 editions keeps the calculation radii, their thresholds and the It/Wt formulas; the CHS
  clause and the size tables of the 2019 editions were not checked.
- The series contain manufacturer sizes that are not in the size tables of the standards (e.g. hot-finished t = 2.9, 3.6,
  4.5, 5.6, 7.1, 8.8, 11, 17.5 mm); `standard` names the series they belong to, not a claim that every size is in the standard.
- CHS: a size is included only if its outside diameter belongs to the diameter series of the product standards — 21.3,
  26.9, 33.7, 42.4, 48.3, 60.3, 76.1, 88.9, 101.6, 114.3, 139.7, 168.3, 177.8, 193.7, 219.1, 244.5, 273, 323.9, 355.6,
  406.4, 457, 508, 610, 711, 762, 813, 914, 1016, 1067, 1168, 1219 mm (EN 10210-2:2006 Table B.1, EN 10219-2:2006 Table C.1,
  identical in both). Wall thicknesses are not restricted. The rule applies to CHS-HF and CHS-CF alike.
- Hot-finished RHS 80x40x11 and RHS 80x40x12.5 are not included: with the EN 10210-2 radii (ri = t) the inner flat
  b − 2t − 2ri is −4 mm and −10 mm, so the outline does not exist. Infeasible geometry is never cut or corrected; an explicit
  ri would need a primary source and an entry in `[corner_radii_overrides]`.
- Six hot-finished RHS have an inner flat of exactly 0 mm (semicircular inner ends): 70x40x10, 80x40x10, 70x50x12.5,
  80x50x12.5, 90x50x12.5, 100x50x12.5 — valid outlines.

### Channels and taper-flange I sections (UPN, UPE, IPN)

- Shapes: UPN `U_TAPERED` (sloped inner flange faces), UPE `U` (parallel flanges), IPN `I_TAPERED`; all `hot_rolled`;
  designations `UPN {h}` (alias `UNP {h}`), `UPE {h}`, `IPN {h}`.
- `standard` = `EN 10365:2017` (as the I sections; superseded by EN 10365:2026, not checked). EN 10365 gives h, b, tw, tf
  and A and leaves the fillet and toe radii to the manufacturers; the radii of the data are those of the national dimension
  standards DIN 1026-1:2009 (UPN), DIN 1026-2:2002 (UPE) and DIN 1025-1:2009 (IPN 80 … 550; IPN 600 is not in it).
- Position of tf (x_tf, measured from the flange tip) and slope: UPN h ≤ 300: x_tf = b/2, 8 %; UPN h > 300 (320 … 400):
  x_tf = (b − tw)/2, 5 %; IPN: x_tf = b/4, 14 %. Sources: the UPN figure of the ArcelorMittal Sales Programme (measuring point
  u = b/2 for h ≤ 300 and u = (b − tw)/2 for h > 300, slopes 8 % / 5 %); EN 10024:1995 clause 4.4 (taper flange I sections:
  flange thickness at b/4 from the mid-width of the flange); ArcelorMittal: IPN flange slope 14 %.
- UPN 320: r2 = 8.8 mm — the value of DIN 1026-1:2009 as printed by the sources that cite it (older editions print
  8.75 = r1/2; the difference changes A by 0.004 %).
- IPN radii are the printed dimensions: r1 = tw, and r2 ≈ 0.6·tw rounded to 0.1 mm is only an observation, not a rule —
  IPN 550 has the printed r2 = 11.9 mm (DIN 1025-1:2009, ArcelorMittal), not 0.6 × 19 = 11.4.

### Angles (L-EQ, L)

- Shapes: L-EQ `L_EQ` (b, t, r1, r2), L `L` (h, b, t, r1, r2; h is the longer leg); `hot_rolled`; designations
  `L {b}x{b}x{t}` and `L {h}x{b}x{t}` (long leg first, as EN 10056-1 and the catalogues; alias `LNP …`).
- The two series are a mixed catalogue range, not the range of one standard: EN 10056-1:1998 gives the geometry and
  calculation convention (sharp heel, r2 = r1/2 by the Note 1 under Tables 1 and 2) and 43 of the 81 sizes; the others are
  DIN 1028 / DIN 1029 or manufacturer sizes. EN 10056-1:2017 supersedes the 1998 edition. The EN 10056-1:1998 sizes:
  equal legs 40x40x4, 40x40x5, 50x50x5, 50x50x6, 60x60x6, 60x60x8, 65x65x7, 70x70x7, 75x75x8, 80x80x8, 80x80x10, 90x90x9,
  100x100x10, 100x100x12, 120x120x10, 120x120x12, 130x130x12, 160x160x15, 180x180x16, 180x180x18, 200x200x16, 200x200x18,
  200x200x20, 200x200x24; unequal legs 50x30x5, 60x30x5, 60x40x5, 60x40x6, 70x50x6, 75x50x6, 80x40x6, 80x40x8, 100x50x6,
  100x50x8, 100x65x7, 120x80x8, 120x80x10, 120x80x12, 150x75x9, 150x100x10, 150x100x12, 200x100x10, 200x100x12.
- Radii follow the strongest documented source; four rows are noted:
  - L 150x75x11: r1 = 10.5, r2 = 5.5 (DIN 1029; the only row with r2 ≠ r1/2) — they reproduce the DIN values A 23.6 cm²,
    Iy 545 cm⁴, Iz 93.0 cm⁴;
  - L 150x100x14: r1 = 12, r2 = 6 — the geometry printed by the ArcelorMittal Sales Programme ("in accordance with DIN 1029",
    r2 = r1/2 by its footnote) and the ArcelorMittal Orange Book; only 12 / 6 reproduces their Iy 744.4, Iz 264.9 and
    IT 22.9 cm⁴ (the DIN 1029 value 13 / 6.5 gives 743.5, 264.2, 23.1);
  - L 110x110x10: r1 = 13, r2 = 6.5 — EN 10056-1:2017 Table 1 prints r = 13 for this designation, and only 13 / 6.5 reproduces
    its A 21.2 cm², c 3.06 cm and I 238 cm⁴ (the withdrawn DIN 1028 value 12 / 6 gives c 3.07, I 239);
  - L 75x50x7: r1 = 7, r2 = 3.5 — unresolved: one stockholder table gives 6.5 / 3.5 (its A 8.30 cm² fits 6.5: 8.298 vs
    8.313); a primary DIN 1029 table would decide.

### Flat bars (FLAT)

- 62 sizes: widths 160, 165, 170, 180, 200, 220, 230 mm, thicknesses 5 … 50 mm (b/t = 3.6 … 40), whole millimetres.
- The sizes are assumed to be hot-rolled flat bars of EN 10058, whose size ranges were not checked; `standard` states this
  assumption and `process` = `hot_rolled` is part of it. No property depends on the process.
- Designation `FLAT {b}x{t}` (aliases `FLAT{b}x{t}`, `FL {b}x{t}`, `STRIP{b}x{t}`).
