# 0004 — BSL 1.1 license, Apache 2.0 after 4 years

- **Status:** accepted (amended 2026-08-31, see *Amendment 1*)
- **Date:** 2026-04-27
- **Tags:** licensing

## Context

DentalPin is open source and intends to grow a community. We also fund
development through a managed SaaS deployment and partner integrators.
A permissive license alone (Apache 2.0, MIT) lets a competing SaaS take
the codebase and operate it without contributing back, undermining the
funding model that pays for ongoing development. A pure copyleft (AGPL)
deters integrators and partner clinics from contributing.

The Business Source License 1.1 (BSL) is the middle ground used by
HashiCorp, MariaDB, CockroachDB, and Sentry: source-available, free for
non-competitive use, with an automatic conversion to a true OSS license
after a fixed number of years.

## Decision

DentalPin is licensed under **BSL 1.1**. Per-version conversion: each
released version becomes **Apache 2.0** four years after its release
date.

Use restriction (BSL "Additional Use Grant"): non-production use is
unrestricted; production use is permitted **except** for offering a
commercial managed dental clinic management service to third parties
that is substantially similar to DentalPin's own SaaS.

The Veri\*Factu module (and any other compliance module) inherits the
same license terms.

## Consequences

### Good

- Source remains fully visible and modifiable by any clinic, and
  self-hostable for evaluation and non-production use. Production
  self-hosting is licensed, not free — see *Amendment 1*.
- Funding model is protected for 4 years per release, after which the
  community gets a true OSS license on that version.
- Contributors know the license trajectory upfront — no rug-pulls.

### Bad / accepted trade-offs

- Some downstream packagers (Linux distros, OSS catalogs) won't list us
  while versions are under BSL.
- Commercial competitors must negotiate a commercial license or wait
  the 4 years. We're fine with that.
- Contributor License Agreement (CLA) required so the relicense
  conversion is unambiguous.

## Amendment 1 — production self-hosting is licensed (2026-08-31)

Two things were wrong with this ADR as accepted, and they turned out to
be the same thing.

**The licence text does not grant what this ADR describes.** The BSL
Terms grant the right to copy, modify, redistribute and make
**non-production** use of the work, and permit production use only
through an *Additional Use Grant*. `LICENSE` contains no Additional Use
Grant. The "Use Limitation" line in its header is a non-standard field
that reads as though production self-hosting were permitted to everyone
except a competing SaaS, and the Consequences above went further and
called the work "self-hostable by any clinic". Neither statement is
supported by the file.

**The business model now depends on the difference.**
[ADR 0028](0028-self-hosting-is-the-premium-tier.md) makes
self-hosting the premium tier, sold and activated by a signed licence
key, on the reasoning that `self` is the only custody mode whose
guarantee actually holds and the one where we hold none of the clinic's
data. Free production self-hosting and a paid self-hosted tier cannot
both be true.

**The rule from here:** non-production and evaluation use stays free and
unrestricted, as the BSL Terms already provide. Production use — a
clinic running DentalPin against real patients, self-hosted or
otherwise — requires a commercial licence. Offering DentalPin as a
competing managed service remains excluded at any price.

`LICENSE` now says this in the form BSL expects: the non-standard "Use
Limitation" field has been replaced by a real **Additional Use Grant**
permitting production use only under an authorization the Licensor issues
(the trial/token path) or a separate commercial licence, with
"production use" defined as running a clinic on real records. The
competing-managed-service exclusion survives inside the grant rather than
as a stray field.

**The draft has not been reviewed by counsel**, and two structural
questions in the file are outside what drafting can fix: the Licensor is
named as "DentalPin Contributors", which is not a legal entity able to
grant a commercial licence or issue a key, and the Change Date now reads
per version, which is what this ADR always intended but changes what a
distributor must track. Anyone already running a production deployment
under the previous reading should be grandfathered by name in an issued
key rather than argued with — deliberately kept out of the licence text,
where it would be permanent and unadministrable.

## Alternatives considered

- **Apache 2.0 from day one.** Rejected: no protection against a SaaS
  fork undercutting the funding model that pays maintainers.
- **AGPLv3.** Rejected: deters partner integrators and self-hosting
  clinics, even though network-clause concerns are mostly theoretical.
- **Pure proprietary.** Rejected: incompatible with the project mission
  of open clinical software.

## How to verify the rule still holds

- `LICENSE` at repo root carries an Additional Use Grant matching
  *Amendment 1*. It does; what it has not had is a lawyer.
- Per-release `LICENSE-CONVERSION-DATES.md` (when introduced) lists the
  Apache 2.0 conversion date for each released version.

## References

- [ADR 0028](0028-self-hosting-is-the-premium-tier.md) — the tier that
  depends on this amendment
- `LICENSE`
- BSL spec: <https://mariadb.com/bsl11/>
- HashiCorp BSL FAQ — used as reference for the additional-use grant
  wording
