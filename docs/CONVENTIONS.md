# Conventions of computed properties

Every published property carries a status and a method id (`properties_meta` in the web JSON).

- `supported` — value computed with the named, versioned method.
- `unsupported` — value `null`, method `null`: no reproducible, cited convention exists for this shape, or (Wpl_y, Wpl_z of
  angles) the computed value has no safe meaning as a section property of the shape. There is no `approximate` status; it
  could only be introduced with a new contract version and a clear public flag.

Exact properties use the shape's exact method. Convention-dependent properties (It, Wt, Iw, ym) are `unsupported` by default;
a series publishes one only by declaring it in `[conventions]` of its TOML with a method implemented for its shape
(`section_properties/conventions.py`). A method is registered only if it has a printed, publicly accessible source, a
precisely defined formula, reproduces printed catalogue values, and its implementation is checked against an independently
written form in the tests.

A method id never changes meaning; a different formula gets a new id (`…_V2`). FEM results (sectionproperties) are
cross-check information only: they are never published and never used as a fallback for `unsupported`.

Consumers (e.g. design calculators) may use only `supported` values and must fail explicitly on `null`, never substitute a
value. Quantities of a design layer — shear area Av, c/t ratios, section class, buckling reduction χ, Mcr, corrosion — are
outside this engine.

## Frame and sign conventions

- Cross-section frame (y, z) in mm, y horizontal (to the right), z vertical (up); EN 1993-1-1 axes.
- `Iy = ∬ (z − z_c)² dA` — second moment about the centroidal y axis (major axis of an I-section).
- `Iz = ∬ (y − y_c)² dA`, `Iyz = ∬ (y − y_c)(z − z_c) dA`.
- Principal axes: I about an axis at the angle a from +y is `Iy·cos²a + Iz·sin²a − 2·Iyz·sin a·cos a`; `Iu` = its maximum,
  `Iv` = its minimum (`Iu ≥ Iv`); `alpha` = angle from +y to the major axis u, counter-clockwise, in (−90°, 90°],
  `alpha = ½·atan2(−2·Iyz, Iy − Iz)`; v is u turned by +90°; `i_u = √(Iu/A)`, `i_v = √(Iv/A)`.
  - Shapes symmetric about their y axis (all except the angles; `SYMMETRIC_ABOUT_Y`): `compute_profile` verifies the symmetry
    (|z_top − z_bottom| ≤ 1e-9·L, |Iyz| ≤ 1e-9·L⁴, L = the largest extent) and publishes `Iyz = 0` exactly, `Iu = max(Iy, Iz)`,
    `Iv = min(Iy, Iz)`, `alpha = 0` (90° if Iz > Iy, which no current row has; the computed Iyz is rounding noise).
  - Flat bars (`FLAT`) stand on edge (width b along z, thickness t along y): y-y is their strong axis, as for the I
    sections — `alpha = 0°`, `Iu = Iy`, `Iv = Iz`. A bar used lying flat is a choice of the consuming application, not a second
    set of data.
  - Isotropic tensors (SHS, CHS: Iy = Iz, Iyz = 0): every axis is principal; `alpha = 0` by convention when
    (Iu − Iv)/2 ≤ 1e-9·(Iy + Iz)/2.
  - Angles: Iyz < 0 and 0° < alpha ≤ 45° (45° for equal legs, to rounding).
- Local frames ([DATA_MODEL.md](DATA_MODEL.md#axes-and-units)): doubly symmetric shapes (flat bars included) centred at the
  origin; channels with the back of the web at y = 0 and the flanges toward +y; angles with the heel at the origin, leg h along
  +z and leg b along +y. `ys` = y_c − y_min and `zs` = z_c − z_min, the centroid measured from the extreme fibres with the
  smallest y and z (channels: the catalogue ys from the back of the web; angles: the catalogue ys, zs from the backs of leg h
  and leg b). `ym` = y_M − y_c, the shear centre measured from the centroid along y (channels: negative, behind the web) —
  unsupported for every series.

### Catalogue notation of angles

- Centroid: our ys, zs = ArcelorMittal "ys", "zs" = SCI P363 / Blue Book "cz", "cy" = EN 10056-1:1998 "cy", "cx".
- `tan(alpha)` is the catalogue tan α (Blue Book: axis y-y to axis u-u; EN 10056-1:1998: between the axes Y-Y and V-V;
  ArcelorMittal: α between z and v — the same angle). ArcelorMittal prints Iyz negative in its own axes (y pointing left,
  z down), the same sign as ours.
- `Wel_y = Wel_y_top` (tip of leg h) and `Wel_z = Wel_z_right` (tip of leg b) are the catalogue Wel,y and Wel,z (the toe fibres;
  SCI P363 §3.2.3); both fibres of both axes are published. Moduli about the principal axes (Wel_u, Wel_v) are not published.
- Catalogue u/v values are not exact geometry: ArcelorMittal prints A, Iy and Iz of the exact geometry with r2 = r1/2, but
  |Iyz| 0.1 … 0.9 % larger (Iv −0.2 … −1.2 %, Iu +0.03 … +0.3 %, alpha +0.01 … +0.07°; L 100x100x10: Iyz −104.0, Iv 72.66 cm⁴
  against the exact −103.67, 73.01); EN 10056-1:2017 Table 1 shows the same bias in most rows. No other geometry assumption
  reproduces them. Our values follow the geometry; printed Iu, Iv, Iyz and tan α are used in the tests only where they agree
  with it.

## Methods

| Method id | Properties | Definition |
|---|---|---|
| `EXACT_CONTOUR_V1` | A, perimeter, ys, zs, Iy, Iz, Iyz, Iu, Iv, alpha, Wel_y, Wel_y_bottom, Wel_y_top, Wel_z, Wel_z_left, Wel_z_right, Wpl_y, Wpl_z (not for angles), i_y, i_z, i_u, i_v | exact integration over the true boundary (straight lines and circular arcs) |
| `MASS_RHO_V1` | mass_per_length | A · 10⁻⁶ · rho, rho = 7850 kg/m³ |
| `IT_ROLLED_I_FILLET_V1` | It (shape `I`, rolled, parallel flanges) | catalogue convention (DIN / *Stahl im Hochbau* tradition) |
| `IW_I_FLANGES_V1` | Iw (shape `I`, parallel flanges) | catalogue convention, flanges only (thin-walled) |
| `IT_ROLLED_U_FILLET_V1` | It (shape `U`, rolled channels with parallel flanges) | catalogue convention of parallel flange channels (SCI P363 / ArcelorMittal Orange Book) |
| `IT_ROLLED_L_FILLET_V1` | It (shapes `L_EQ`, `L`, rolled angles) | catalogue convention of angles (SCI P363 §3.2.6 / Blue Book / Orange Book) |
| `IT_HOLLOW_EN_V1` | It, Wt (shapes `SHS`, `RHS`) | formula of EN 10210-2 / EN 10219-2 (Bredt + open strip, mean corner radius) |
| `IT_CHS_EXACT_V1` | It, Wt (shape `CHS`) | exact: polar moment 2·I and 2·Wel of the annulus |

Wt is the torsional modulus [mm³] (the product standards' "Ct"; T/Wt is the nominal shear stress of the standards, not the peak
stress at the re-entrant corners). It is a property of every series, `unsupported` where no method is registered.

### `EXACT_CONTOUR_V1`

- **Area and moments.** A, first and second moments are boundary integrals (Green's theorem) over the exact lines and arcs,
  in closed form. Arcs are never replaced by chords.
- **Elastic modulus.** `Wel_y = Iy / max(z_top, z_bottom)` and `Wel_z = Iz / max(y_right, y_left)`, i.e. the minimum of the
  two extreme fibres. Both fibres of both axes are published as well: `Wel_z_left = Iz / y_left`,
  `Wel_z_right = Iz / y_right`, `Wel_y_bottom = Iy / z_bottom`, `Wel_y_top = Iy / z_top` (y_left = ys, z_bottom = zs;
  channels: back of the web and flange tips, Wel_z = Wel_z_right). The two y fibres are equal for every shape symmetric about
  y; for angles Wel_y = Wel_y_top and Wel_z = Wel_z_right are the moduli at the leg tips (the catalogue values). Moduli about
  the principal axes u, v are not published.
- **Plastic modulus.** `Wpl` is the sum of the first moments of the two equal-area parts about the plastic neutral axis, which
  is parallel to the named axis (y or z). The PNA is found by bisection with a fixed number of iterations; the area above a
  trial cut is an exact boundary integral. For a section that is not symmetric about that axis (angles) the PNA does not pass
  through the centroid, and the same fully plastic stress block also has a moment about the other axis: Wpl_y·fy is the
  largest My of the plastic interaction surface (accompanied by an Mz), not the plastic resistance to bending about y alone,
  which needs an inclined neutral axis and is smaller (Wpl_y / W_free = 1.19 … 1.26 for L 100x100x10, L 150x75x9,
  L 200x100x10). Wpl_y, Wpl_z are not principal-axis values either. They are therefore not published for angles
  (`unsupported`, null), so that no consumer uses them like the Wpl of an I or hollow section; the engine still computes them
  for the tests. No angle catalogue prints Wpl (SCI P363 tabulates Wpl "for all sections except angle sections").
- **Radius of gyration.** `i = √(I / A)`.
- **Hollow sections.** SHS/RHS: outer rounded rectangle minus the inner one, with the corner radii of the series rule; CHS:
  two exact circles — the engine gives the textbook annulus formulas to rounding (`tests/test_shape_hollow.py`,
  rel ≤ 1e-9).
- **Plastic neutral axis.** The bisection evaluates only the area above each trial cut; the area of every boundary piece is
  computed with the same arithmetic as the full moments and summed with `math.fsum`, so the result is bit-identical to
  evaluating all moments (checked on every profile).
- **Perimeter.** Length of the outer boundary [mm]. The catalogue "surface per metre" [m²/m] equals perimeter / 1000.
- **Sloped flanges** (`U_TAPERED`, `I_TAPERED`): the inner flange faces are straight lines through the point where tf is
  measured (x_tf from the tip), the root fillets and toe arcs are exact circular arcs tangent to them
  (`section_properties/shapes/channel.py`). The engine equals an independent slice integration with Gauss-Legendre quadrature
  to rounding (`tests/test_shape_channel.py`).
- **Angles** (`L_EQ`, `L`): sharp heel, root fillet r1, toe arcs r2 at the inner edges of the leg ends
  (`section_properties/shapes/angle.py`). Every published value equals an independent computation (`tests/angle_reference.py`:
  analytic decomposition, Gauss-Legendre slices, eigen-decomposition) to rounding (`tests/test_shape_angle.py`).
- **Flat bars** (`FLAT`): a solid rectangle b × t with sharp corners, on edge (`section_properties/shapes/flat.py`). Every
  published value equals the closed form of the rectangle (`tests/flat_reference.py`: A = b·t, Iy = t·b³/12, Iz = b·t³/12,
  Wel = t·b²/6 and b·t²/6, Wpl = t·b²/4 and b·t²/4, i = b/√12 and t/√12). Both plastic neutral axes are axes of symmetry, so
  — unlike the angles — the fully plastic stress block has no moment about the other axis.

### `MASS_RHO_V1` — mass per unit length

```
mass_per_length [kg/m] = A [mm²] · 10⁻⁶ [m²/mm²] · rho [kg/m³],   rho = 7850 kg/m³
```

The symbol `G` is not used for mass (it is reserved for the shear modulus).

### `IT_ROLLED_I_FILLET_V1` — St Venant torsion constant of rolled I/H sections (convention)

```
It = 2/3·(b − 0.63·tf)·tf³ + 1/3·(h − 2·tf)·tw³ + 2·(tw/tf)·(0.145 + 0.1·r/tf)·D⁴      [mm⁴]
D  = [(r + tw/2)² + (r + tf)² − r²] / (2·r + tf) = [(tf + r)² + tw·(r + tw/4)] / (2·r + tf)
```

- Terms: two flanges as thin rectangles with the end correction 0.63·tf (a·b³/3·(1 − 0.63·b/a)); the web between the
  flanges; two web–flange junctions (coefficient α = (tw/tf)(0.145 + 0.1·r/tf), D = diameter of the circle inscribed in the
  junction — the junction method of Trayer & March).
- Sources: ArcelorMittal Europe – Long Products, *Sections and Merchant Bars* Sales Programme "Version 2014-x", p. 216
  "Notations and formulae" (declared "only valid for I and H sections with parallel flanges", p. 215); Wagner W., Sauer R.,
  Gruttmann F.: *Tafeln der Torsionskenngrößen von Walzprofilen unter Verwendung von FE-Diskretisierungen*, Mitteilung
  5(1999), Institut für Baustatik, Universität Karlsruhe (also Stahlbau 68(2) 1999, 102–111), eqs. (13), (16), (18), citing
  *Stahl im Hochbau* 14th ed. Vol. I/Part 2 (1986) — the DIN 1025 table values were computed with this formula; the same in
  Wagner & Gruttmann, Mitteilung 9(2002), eqs. (11)–(14); the Peiner Träger IPB/HE delivery programme (2009).
- The origin of the constant 0.145 is not documented (Roark's linear fit of the NACA Report 334 graph uses 0.15, which would
  raise It by 0.30–0.57 %).
- Printed values reproduced (`tests/test_torsion.py`): IPE 80 0.70, IPE 300 20.1, HE 300 A 85.17, HE 300 B 185.0,
  HE 300 M 1408 cm⁴ (ArcelorMittal "Version 2014"); HE 1000 M 1701 cm⁴ (Peiner 2009).
- It is a convention, not the exact value: vs exact St Venant values (FE, Karlsruhe 1999) it deviates by IPE +0.4…+4.3 %,
  HEA −2.7…+3.1 %, HEB −2.1…0.0 %, HEM −1.2…+1.4 % (the FEM cross-check gives the same ranges). The current ArcelorMittal
  catalogue (2021–2026-1) uses the junction coefficient of El Darwish & Johnston (1965) as printed in SCI P385 (2011) instead,
  −3.0…+3.8 % different (e.g. HE 300 A 85.17 vs 87.76 cm⁴, IPE 80 0.698 vs 0.672 cm⁴); that variant is not adopted — it would
  be a new method id.
- Scope: rolled I and H sections with parallel flanges.

### `IW_I_FLANGES_V1` — warping constant of doubly symmetric I sections (convention)

```
Iw = tf·b³·(h − tf)² / 24  =  Iz,flanges·(h − tf)² / 4,   Iz,flanges = 2·tf·b³/12      [mm⁶]
```

- Flanges only (thin-walled theory; web, fillets and flange thickness neglected in the warping function), h − tf = distance
  between the flange mid-planes.
- Sources: ArcelorMittal Sales Programme 2021, 2023, 2024-1 p. 171 and V2026-1 p. 176 ("Iw = tf b³/24 (h − tf)²", the same
  "parallel flanges" scope note; the tables of every edition follow it); Wagner, Sauer & Gruttmann 1999 eq. (22),
  attributed to *Stahl im Hochbau* and *Bautabellen*; SCI P385 (Hughes, Iles, Malik, *Design of steel beams in torsion*,
  2011), App. B.3.1: Iw = If·(h − tf)²/2.
- The UK variant Iz·hs²/4 with the whole-section Iz (SCI P363, NCCI SN003b) is 0.12–0.72 % larger and is not used.
- Printed values reproduced (`tests/test_torsion.py`; ArcelorMittal V2026-1, which truncates to the digits shown), e.g.
  IPE 200 12.98, HE 300 A 1199, HE 1000 M 43010 ×10³ cm⁶.
- It is a convention: 0.75–5.25 % above exact (FE) warping constants (FEM cross-check, all I sections), most for thick HE M
  flanges.

### `IT_ROLLED_U_FILLET_V1` — St Venant torsion constant of rolled channels with parallel flanges (convention)

```
It = 2/3·b·tf³ + 1/3·(h − 2·tf)·tw³ + 2·α3·D3⁴ − 0.42·tf⁴                                  [mm⁴]
α3 = −0.0908 + 0.2621·tw/tf + 0.1231·r/tf − 0.0752·tw·r/tf² − 0.0945·(tw/tf)²
D3 = 2·[(3·r + tw + tf) − √(2·(2·r + tw)·(2·r + tf))]
```

- Terms: flanges and web as thin rectangles; two web–flange corners with the junction coefficient α3 of El Darwish & Johnston
  and D3 = the diameter of the largest circle inscribed in the corner (tangent to the back of the web, the outer flange face
  and the root fillet — derived independently in `tests/test_torsion.py`); −0.42·tf⁴ the deduction for the flange tips as
  printed.
- Sources: SCI P363 *Steel building design: Design data* (2015 reprint), explanatory notes §3.2.6 (pp. A-5 … A-6), printed
  "applicable to parallel flange channels only"; the same formula in the ArcelorMittal Orange Book (UK NA) §3.2.6 and the Steel
  for Life Blue Book. It reproduces the printed It of all 14 UPE of the ArcelorMittal Sales Programme and the Orange Book to
  their three significant digits (e.g. UPE 80 1.47, UPE 200 8.89, UPE 400 79.1 cm⁴; `tests/test_torsion.py`).
- It is a convention: SCI P385 (2011) App. B.2.2 argues that one deduction of 0.21·tf⁴ per free tip would be consistent; that
  variant is 2.8 … 3.7 % higher (UPE 400: 81.3 instead of the printed 79.1 cm⁴) and does not reproduce the catalogue values.
  The exact St Venant J of the outline (FEM cross-check) is 0.43 % below … 0.05 % above the formula.
- Scope: parallel flange channels (shape U). Not for sloped (tapered) flanges.

### `IT_ROLLED_L_FILLET_V1` — St Venant torsion constant of rolled angles (convention)

```
It = 1/3·b·t³ + 1/3·(h − t)·t³ + α3·D3⁴ − 0.21·t⁴                                          [mm⁴]
α3 = 0.0768 + 0.0479·r1/t
D3 = 2·[(3·r1 + 2·t) − √(2·(2·r1 + t)²)]
```

- Terms: the two legs as thin rectangles (the heel counted once); the L junction at the heel with the coefficient α3 of
  El Darwish & Johnston (the channel coefficient of `IT_ROLLED_U_FILLET_V1` with tw = tf = t) and D3 = the diameter of the
  largest circle inscribed in the heel (tangent to both outer faces and to the root fillet); −0.21·t⁴ = 0.105·t⁴ for each of
  the two free leg ends. The toe radius r2 is not used.
- Sources: SCI P363 *Steel building design: Design data* (2015 reprint), explanatory notes §3.2.6 "Angles", p. A-7; the same
  formula in the Steel for Life Blue Book and the ArcelorMittal Orange Book; SCI P385 (2011) App. B.2.2 pp. 64-65 (the general
  L-junction coefficient of El Darwish & Johnston, ASCE J. Struct. Div. 91(ST1), 1965, and the deduction 0.105·t⁴ per free
  end). It reproduces every printed IT of the angle tables of SCI P363 (81 UK sizes) and 221 of 224 angles of the Orange Book
  (the other three are t = 3 mm rows displayed with three decimals) to their printed digits; 19 printed values of our sizes
  are recorded in `tests/test_torsion.py` (e.g. L 100x100x10 6.97, L 200x200x24 182, L 150x100x14 22.9,
  L 110x110x10 7.74 cm⁴).
- It is a convention: about 2 % above exact (FE) St Venant values (Wagner, Sauer & Gruttmann 1999, Tables 7/8; FEM cross-check
  1.7 … 3.2 %) and 4.7 … 15.7 % above the thin-walled (h + b − t)·t³/3. It depends on r1.

### `IT_HOLLOW_EN_V1` — torsion constant and modulus of rectangular hollow sections

```
Rc = (ro + ri) / 2                              mean corner radius (radii of the series rule, unrounded)
p  = 2·[(b − t) + (h − t)] − 2·Rc·(4 − π)       perimeter of the wall mid-line (the standards' "h")
Ah = (b − t)·(h − t) − Rc²·(4 − π)              area enclosed by the wall mid-line
K  = 2·Ah·t / p
It = t³·p/3 + 2·K·Ah                            [mm⁴]
Wt = It / (t + K/t)                             [mm³]   (the standards' Ct)
```

- Sources: EN 10210-2:2006 A.3 and EN 10219-2:2006 B.3 (identical formulae; clause A.3 of the 2019 editions unchanged);
  SCI P363 §3.3.3/3.3.4. Printed values of Vallourec *MSH Technical Information 1* (2012, hot finished), Tata Steel *Hybox 355*
  technical guide (2010, cold formed) and SSAB structural hollow sections (2016, cold formed; rows with t ≠ 7.1, whose radii
  that catalogue rounds) are reproduced to the printed digits (`tests/test_torsion.py`). Alternative conventions (thin-walled
  Bredt without the corner correction, sharp corners) reproduce almost none of the European catalogue rows.
- Terms: t³·p/3 is the St Venant constant of the open wall strip, 2·K·Ah = 4·Ah²·t/p Bredt's constant of the closed cell.
- It is a convention: the exact St Venant J of the outline (FEM cross-check) is 0.5–7 % higher for hot-finished sections
  (their non-concentric corners are thicker than the mid-line model) and within about ±0.3 % for cold-formed ones.
- Wt is nominal: the elastic shear stress concentrates at the re-entrant corners and can exceed T/Wt considerably; T/Wt is
  not the maximum shear stress at the corners.

### `IT_CHS_EXACT_V1` — circular hollow sections

```
It = π·(D⁴ − d⁴) / 32 = 2·I      Wt = It / (D/2) = 2·Wel      d = D − 2·t
```

Exact for an annulus (the St Venant warping function is zero, so the torsion constant is the polar moment and the largest shear
stress T·(D/2)/It occurs at the outer surface); also the definition of EN 10210-2:2006 A.2 and EN 10219-2:2006 B.2 (It = 2I,
Ct = 2Wel).

## Unsupported properties

A candidate below can be adopted later only as a new method id that meets the registration criteria above.

- **ym (shear centre), every series.** No method is registered for any shape and the web schema rejects a supported ym. The
  contract carries only the offset along y; publishing the shear centre of an angle would also need zm (a new contract
  version).
- **Wt of open sections** (I, U, U_TAPERED, I_TAPERED, L_EQ, L) **and of flat bars**: no convention.
- **Iw of hollow sections**: not registered (CHS: zero in theory).
- **It of UPN and IPN; Iw of UPN, UPE and IPN.** The catalogue values are the DIN 1025-1 / DIN 1026 table values (computed by
  Bornscheuer, Stahlbau 30(3), 1961, as quoted in Wagner, Sauer & Gruttmann 1999, Tab. 1 and 6); their method could not be
  reproduced. The ArcelorMittal Sales Programme prints formulas only for I and H sections with parallel flanges; SCI P363 and
  the Orange Book print It and Iw formulas for parallel flange channels, "not for tapered flange channels" — their It
  reproduces the printed It of UPE (adopted as `IT_ROLLED_U_FILLET_V1`), their Iw does not reproduce the UPE table Iw
  (+6 … +14 %), nor does the thin-walled channel formula (+3 … +8 %). For UPN no formula reproduces It (SCI channel formula
  −1.4 … +2 %), Iw or ym; for IPN no printed formula reproduces It (the I-section formulas −4.5 … −11 %). Exact FE values exist
  (Wagner et al. 1999) but are not a catalogue convention. Candidates not adopted: IPN Iw = If·(h − tf)²/2 with If of the
  sloped flange (reproduces the table Iw within −0.25 … +0.19 %, but applying the printed general formula Iw = If·hs²/2 to
  sloped flanges is an inference, not a printed convention); UPE ym by the thin-walled channel formula (mid-line dimensions
  b − tw/2, h − tf; reproduces the table ym within ±0.12 %, but no source prints it as the method).
- **Iw of angles.** No European catalogue prints a warping constant of angles; thin-walled theory gives zero; the thick-walled
  t³/36·[(b − t/2)³ + (h − t/2)³] (CISC 2002) is no European convention.
- **Shear centre of angles.** No catalogue prints its position; the thin-walled convention S1 (the intersection of the leg
  mid-lines) differs from the exact shear centre by several mm for the larger sizes.
- **It, Wt, Iw of flat bars.** The exact St Venant constant of a solid rectangle has no closed form; it is the series
  It = b·t³/3 · [1 − 192·t/(π⁵·b) · Σ (n = 1, 3, 5, …) tanh(n·π·b/(2·t))/n⁵] (b ≥ t). The thin-strip b·t³/3 is its limit for
  b/t → ∞ and overestimates it over the data by 1.6 % (b/t = 40) to 21.2 % (b/t = 3.6); it is not published. Wt is a series
  as well; Iw is zero for a single straight wall in thin-walled theory.
- **Wpl_y, Wpl_z of angles**: see `EXACT_CONTOUR_V1` above.

## Status per series

All other properties (A, mass_per_length, perimeter, ys, zs, Iy, Iz, Iyz, Iu, Iv, alpha, the Wel moduli, the radii of
gyration) are `supported` (`EXACT_CONTOUR_V1`, mass `MASS_RHO_V1`) for every series.

| Series | Shape | It | Wt | Iw | ym | Wpl_y, Wpl_z |
|---|---|---|---|---|---|---|
| IPE, HEA, HEB, HEM | `I` | `IT_ROLLED_I_FILLET_V1` | unsupported | `IW_I_FLANGES_V1` | unsupported | supported |
| SHS-HF, SHS-CF | `SHS` | `IT_HOLLOW_EN_V1` | `IT_HOLLOW_EN_V1` | unsupported | unsupported | supported |
| RHS-HF, RHS-CF | `RHS` | `IT_HOLLOW_EN_V1` | `IT_HOLLOW_EN_V1` | unsupported | unsupported | supported |
| CHS-HF, CHS-CF | `CHS` | `IT_CHS_EXACT_V1` | `IT_CHS_EXACT_V1` | unsupported | unsupported | supported |
| UPE | `U` | `IT_ROLLED_U_FILLET_V1` | unsupported | unsupported | unsupported | supported |
| UPN | `U_TAPERED` | unsupported | unsupported | unsupported | unsupported | supported |
| IPN | `I_TAPERED` | unsupported | unsupported | unsupported | unsupported | supported |
| L-EQ, L | `L_EQ`, `L` | `IT_ROLLED_L_FILLET_V1` | unsupported | unsupported | unsupported | unsupported |
| FLAT | `FLAT` | unsupported | unsupported | unsupported | unsupported | supported |

## Output units and rounding

| Output | Units | Rounding |
|---|---|---|
| `generated/web/<ID>.json` | mm, mm², mm³, mm⁴, mm⁶, kg/m; `alpha` in degrees; geometry key `slope_pct` in % | 6 significant figures |
| `generated/properties/<ID>.csv` (audit) | catalogue units: cm², cm³, cm⁴, cm⁶, cm, kg/m, m²/m; `alpha_deg` and `tan_alpha` (`inf` where alpha = 90°; no current row) | 6 significant figures |

Geometry is echoed exactly as written in the data file; corner radii of SHS/RHS are the exact decimal results of the series
rule (1.5 × 6.3 = 9.45), marked in the audit column `corner_radii`. Wt is in mm³ (web) and cm³ (audit column `Wt_cm3`).
Rounding uses ROUND_HALF_EVEN applied to the exact binary value of each float; numbers are written in plain decimal notation
(no exponent). Unsupported properties are `null` in the web JSON and the word `unsupported` in the audit tables.

## Web JSON contract

`schema_version` in `generated/web/<ID>.json` and `generated/web/index.json` is the version of the public web JSON contract,
written from `WEB_SCHEMA_VERSION` in `section_properties/export.py`. The current version is **1**.

- Series files (`generated/web/<ID>.json`), fixed by [`schema/web.schema.json`](../schema/web.schema.json): `schema_version`,
  `series`, `title`, `shape`, `standard`, `process`, `corner_radii` (SHS/RHS only), `units`, `properties_meta` (per property:
  `status`, `method`, and `rho_kg_m3` for the mass), `profiles` (each: `id` = `<series>/<designation>`, `designation`,
  `geometry`, `properties`). The schema enforces value `null` ⇔ status `unsupported` for every property of every profile, the
  corner-radius rule of SHS/RHS and the convention methods registered for each shape.
- `index.json`: `schema_version`, `generator` (`package`, `version` — the package version, independent of the contract
  version) and `series` (entries `id`, `file`, `shape`, `profiles`). It has no schema; its layout is pinned by
  `tests/test_export.py` and belongs to the contract.

Every change of `schema/web.schema.json` other than its descriptions, and every change of the index.json layout, increments
the version — together with the generated files, the schema fingerprint and index layout recorded in `tests/test_export.py`,
and this section. New profiles, series or values that the schema already allows do not. The `schema_version` of the series
TOML files versions an internal input format and is independent of it.

## Verification

- **Identity tests** (`tests/`): the engine against closed forms and analytic identities of every shape. Tolerances
  (`tests/tolerances.toml`) follow math.isclose semantics, |x − ref| ≤ max(rel_tol·max(|x|, |ref|), abs_tol), with
  abs_tol = ε·L^k in the unit of the quantity (k = its dimension exponent): primitives ε = 1e-12, closed forms ε = 1e-9
  (rel 1e-9). L is the characteristic size — max(h, b); for angles the longer leg; for flat bars the thickness t, so that the
  small weak-axis values of thin bars are checked to about 1e-9 relative as well. Tolerances are never widened to make a test
  pass.
- **Independent references**: `tests/angle_reference.py` (angles) and `tests/flat_reference.py` (flat bars) import nothing
  from the engine; the channels and taper-flange I sections are checked against an independent slice integration in
  `tests/test_shape_channel.py`; every convention method against an independently written form in `tests/test_torsion.py`.
- **Control values**: IPE 200 (A, Iy, Iz, Wpl_y, Wpl_z, mass; `tests/tolerances.toml`).
- **Printed catalogue values**: a sample of values printed by EN 10056-1, SCI P363 / Blue Book, the ArcelorMittal Sales
  Programme, Orange Book and UPE brochure, DIN tables, Vallourec, Tata Steel and SSAB is reproduced at the printed precision
  (`tests/test_torsion.py`, `tests/test_catalogue_angles.py`, `tests/test_catalogue_channels.py`).
- **Optional FEM cross-check** (`crosscheck/fem_check.py`, sectionproperties, informative, never blocking, never published):
  I sections with finely tessellated arcs (sagitta ≤ 1e-4 mm, mesh A/15000) against the exact engine; hollow sections on a
  fixed polygon (32 chords per 90°, element area ≤ (t/3)², torsion J with the iterative `cgs` solver), channels, taper-flange I
  sections and angles against the engine evaluated on the same polygon; J, Iw and the shear centre are listed for information.
  Settings: `crosscheck/tolerances.toml`.
