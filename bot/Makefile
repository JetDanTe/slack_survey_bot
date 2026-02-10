ALEMBIC = alembic


PHONY: mm m

mm: # makemigrations
	${ALEMBIC} revision --autogenerate -m "${msg}"

m: # migrate
	${ALEMBIC} upgrade head