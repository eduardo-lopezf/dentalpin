"""professionals: replace free-text specialty with catalog links.

The directory stored ``specialty`` as free text while the same discipline
names were also typed into a hardcoded list in the UI and, since cat_0004,
kept in the ``specialties`` catalog. Three sources for one fact, so a stray
accent silently split a discipline in two — and any feature keying off
"which specialties does my staff cover" was built on that.

Many-to-many, mirroring how treatments are classified: a dentist who does
both endodontics and periodontics is ordinary, and a single column cannot
say so.

Only clinical staff (dentists, hygienists) practise a discipline, so only
their values become catalog entries: each distinct (clinic, specialty) is
matched against the clinic's catalog by name across locales, created when
missing, then linked. Collaborator labels ("Laboratorio", "Proveedor", ...)
are roles rather than specialties — they would show up as empty groups in
the treatment catalog — so they are appended to ``notes`` instead of being
promoted, which keeps the data without polluting the discipline axis.

Only after that does the text column go.

``depends_on`` pins the catalog branch: ``specialties`` must exist before
these FKs can be created.

Revision ID: pro_0002
Revises: pro_0001
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pro_0002"
down_revision: str | None = "pro_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "cat_0004"


def upgrade() -> None:
    op.create_table(
        "professional_specialties",
        sa.Column(
            "professional_id",
            sa.UUID(),
            sa.ForeignKey("professionals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "specialty_id",
            sa.UUID(),
            sa.ForeignKey("specialties.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "idx_professional_specialties_specialty",
        "professional_specialties",
        ["specialty_id"],
    )

    # Preserve collaborator labels as notes: they are roles, not disciplines,
    # and promoting them would put empty groups in the treatment catalog.
    op.execute(
        """
        UPDATE professionals
        SET notes = btrim(concat_ws(E'\n', notes, concat('Perfil: ', btrim(specialty))))
        WHERE professional_type NOT IN ('dentist', 'hygienist')
          AND specialty IS NOT NULL
          AND btrim(specialty) <> ''
        """
    )

    # Create the catalog entries that clinical staff values imply.
    op.execute(
        """
        INSERT INTO specialties (id, clinic_id, names, is_active, created_at, updated_at)
        SELECT gen_random_uuid(),
               d.clinic_id,
               jsonb_build_object('es', d.specialty, 'en', d.specialty),
               true,
               now(),
               now()
        FROM (
            SELECT DISTINCT clinic_id, btrim(specialty) AS specialty
            FROM professionals
            WHERE specialty IS NOT NULL AND btrim(specialty) <> ''
              AND professional_type IN ('dentist', 'hygienist')
        ) d
        WHERE NOT EXISTS (
            SELECT 1 FROM specialties s
            WHERE s.clinic_id = d.clinic_id
              AND EXISTS (
                  SELECT 1 FROM jsonb_each_text(s.names) v WHERE v.value = d.specialty
              )
        )
        """
    )

    # Link every clinical professional to the matching catalog entry.
    op.execute(
        """
        INSERT INTO professional_specialties (professional_id, specialty_id)
        SELECT p.id, s.id
        FROM professionals p
        JOIN specialties s ON s.clinic_id = p.clinic_id
        WHERE p.specialty IS NOT NULL
          AND btrim(p.specialty) <> ''
          AND p.professional_type IN ('dentist', 'hygienist')
          AND EXISTS (
              SELECT 1 FROM jsonb_each_text(s.names) v WHERE v.value = btrim(p.specialty)
          )
        ON CONFLICT DO NOTHING
        """
    )

    op.drop_column("professionals", "specialty")


def downgrade() -> None:
    op.add_column("professionals", sa.Column("specialty", sa.String(length=150), nullable=True))

    # Collapse back to one value: the alphabetically first linked specialty,
    # preferring Spanish. Lossy by nature — the column only holds one.
    op.execute(
        """
        UPDATE professionals p
        SET specialty = sub.name
        FROM (
            SELECT ps.professional_id,
                   MIN(COALESCE(s.names->>'es', s.names->>'en')) AS name
            FROM professional_specialties ps
            JOIN specialties s ON s.id = ps.specialty_id
            GROUP BY ps.professional_id
        ) sub
        WHERE sub.professional_id = p.id
        """
    )

    op.drop_index(
        "idx_professional_specialties_specialty",
        table_name="professional_specialties",
    )
    op.drop_table("professional_specialties")
