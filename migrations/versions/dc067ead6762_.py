"""empty message

Revision ID: dc067ead6762
Revises: 
Create Date: 2020-04-24 20:14:16.045232

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc067ead6762'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('artificial_title',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=True),
    sa.Column('creation_date', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('genre',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=90), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('artist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=True),
    sa.Column('formation_date', sa.DateTime(), nullable=True),
    sa.Column('country', sa.String(length=120), nullable=True),
    sa.Column('genre_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['genre_id'], ['genre.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('artificial_song',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('artificial_title_id', sa.Integer(), nullable=True),
    sa.Column('lyrics', sa.Text(), nullable=True),
    sa.Column('model', sa.String(length=150), nullable=True),
    sa.Column('creation_date', sa.DateTime(), nullable=True),
    sa.Column('base_artist_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['artificial_title_id'], ['artificial_title.id'], ),
    sa.ForeignKeyConstraint(['base_artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('song',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=150), nullable=True),
    sa.Column('lyrics', sa.Text(), nullable=True),
    sa.Column('publication_date', sa.DateTime(), nullable=True),
    sa.Column('artist_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['artist_id'], ['artist.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('song')
    op.drop_table('artificial_song')
    op.drop_table('artist')
    op.drop_table('genre')
    op.drop_table('artificial_title')
    # ### end Alembic commands ###
