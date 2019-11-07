# Metabolic Ninja

![master Branch](https://img.shields.io/badge/branch-master-blue.svg)
[![master Build Status](https://travis-ci.org/DD-DeCaF/metabolic-ninja.svg?branch=master)](https://travis-ci.org/DD-DeCaF/metabolic-ninja)
[![master Codecov](https://codecov.io/gh/DD-DeCaF/metabolic-ninja/branch/master/graph/badge.svg)](https://codecov.io/gh/DD-DeCaF/metabolic-ninja/branch/master)

![devel Branch](https://img.shields.io/badge/branch-devel-blue.svg)
[![devel Build Status](https://travis-ci.org/DD-DeCaF/metabolic-ninja.svg?branch=devel)](https://travis-ci.org/DD-DeCaF/metabolic-ninja)
[![devel Codecov](https://codecov.io/gh/DD-DeCaF/metabolic-ninja/branch/devel/graph/badge.svg)](https://codecov.io/gh/DD-DeCaF/metabolic-ninja/branch/devel)

## Development

Run `make setup` first when initializing the project for the first time. Type
`make` to see all commands.

### Environment

Specify environment variables in a `.env` file. See `docker-compose.yml` for the
possible variables and their default values.

* Set `ENVIRONMENT` to either
  * `development`,
  * `testing`, or
  * `production`.
* `SECRET_KEY` Flask secret key. Will be randomly generated in development and testing environments.
* `SENTRY_DSN` DSN for reporting exceptions to
  [Sentry](https://docs.sentry.io/clients/python/integrations/flask/).
* `ALLOWED_ORIGINS`: Comma-seperated list of CORS allowed origins.

### Updating Python dependencies

To compile a new requirements file and then re-build the service with the new requirements, run:

    make pip-compile build

## Database Migrations

It is important to migrate the database before starting your work and also to
create migrations whenever you change database models.

    make databases
 
The following commands will be useful. Please also read the full 
[documentation online](https://flask-migrate.readthedocs.io/en/latest/).
 
    docker-compose run --rm web flask db init
    docker-compose run --rm web flask db migrate
    docker-compose run --rm web flask db upgrade
    
You also need to create the database and tables like so:

    dock
    >>> from .app import app, init_app
    >>> from .models import db
    >>> init_app(app, db)
    >>> db.create_all()
    
Before deploying the service you should run those commands with the `-e 
ENVIRONMENT=production` or `staging` flag in order to create the required 
tables on our production/staging database.

## Products

The Products API resource lists all the metabolites in the universal model
`cameo.models.universal.metanetx_universal_model_bigg_rhea`. To allow the web
service to avoid loading the large universal models into memory, the list of
metabolites is written to `data/products.json` by the script
`src/scripts/dump_products.py`. This dump must be updated whenever the list of
metabolites in the universal model changes.
