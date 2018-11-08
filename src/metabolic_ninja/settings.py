# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provide settings for different deployment scenarios."""

import os

import requests
import werkzeug.exceptions


__all__ = ("Development", "Testing", "Production")


def current_config():
    """Return the appropriate configuration object based on the environment."""
    if os.environ['ENVIRONMENT'] in ['production', 'staging']:
        return Production()
    elif os.environ['ENVIRONMENT'] == 'testing':
        return Testing()
    elif os.environ['ENVIRONMENT'] == 'development':
        return Development()
    else:
        raise KeyError(f"Unknown environment '{os.environ['ENVIRONMENT']}'")


class Default:
    """Set the default configuration for all environments."""

    def __init__(self):
        """
        Initialize the default configuration.

        We chose configuration by instances in order to avoid ``KeyError``s
        from environments that are not active but access
        ``os.environ.__getitem__``.
        """
        self.DEBUG = True
        self.SECRET_KEY = os.urandom(24)
        self.BUNDLE_ERRORS = True
        self.APISPEC_TITLE = "Metabolic Ninja"
        self.APISPEC_SWAGGER_UI_URL = "/"
        self.CORS_ORIGINS = os.environ['ALLOWED_ORIGINS'].split(',')
        self.SENTRY_DSN = os.environ.get('SENTRY_DSN')
        # TODO: Configure this with the new sentry-sdk
        self.SENTRY_CONFIG = {
            'ignore_exceptions': [
                werkzeug.exceptions.BadRequest,
                werkzeug.exceptions.Unauthorized,
                werkzeug.exceptions.Forbidden,
                werkzeug.exceptions.NotFound,
                werkzeug.exceptions.MethodNotAllowed,
            ]
        }
        self.LOGGING = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simple': {
                    'format': "%(asctime)s [%(levelname)s] [%(name)s] "
                              "%(message)s",
                },
            },
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                },
            },
            'loggers': {
                # All loggers will by default use the root logger below (and
                # hence be very verbose). To silence spammy/uninteresting log
                # output, add the loggers here and increase the loglevel.
            },
            'root': {
                'level': 'DEBUG',
                'handlers': ['console'],
            },
        }
        self.MODEL_STORAGE_API = os.environ["MODEL_STORAGE_API"]
        self.SQLALCHEMY_DATABASE_URI = (
            'postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASS}@{POSTGRES_HOST}:'
            '{POSTGRES_PORT}/{POSTGRES_DB_NAME}'.format(**os.environ)
        )
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.JWT_PUBLIC_KEY = requests.get(
            f"{os.environ['IAM_API']}/keys").json()["keys"][0]
        self.ALGORITHM = 'RS512'


class Development(Default):
    """Development environment configuration."""

    pass


class Testing(Default):
    """Testing environment configuration."""

    def __init__(self):
        """Initialize the testing environment configuration."""
        super().__init__()
        self.TESTING = True
        self.SQLALCHEMY_DATABASE_URI = (
            'postgresql://postgres:@postgres:5432/metabolic_ninja_testing'
        )
        # Note: The private key is only needed for token generation in testing
        self.JWT_PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEA32FY2NFy0yXKMp9aFP8E/oF/4czX2dvrJmOxyG/5OepdHVau\noiE0WCMI7jzm7uYxF98CZNlMXxE0FKqVPchYBydbqMj+L4GxZqMbgUJ19c4HHLNA\nRN1bTlqaQpRZxY/Fsk/xylNRYIgM5QY0lflguPrAY4uOQhriySJSz+tqs/gwdcTZ\nwPZj80v4qE7ZSw0E+ZPP8Cfbmh6uvuM659c18NIl9o6brOTw9BcHmpCEK4JSS759\nLpEPZtUd5jmx5IqLwSKuaQJ0/XXjz4PTKinBrWbTyiaAkL30fKpYAn4sztQbyzMq\nZFe0rec/SlUUkUkwgrbTPpFSnb4dJO3DvVpwYwIDAQABAoIBAClWenqlR/qLI7/6\nfVElYGc4z9GZdth6OioAiQXustBk7pZfVDHssyMcWKq92n6bWrpwKqE/FUMCjADH\nEJc+XAv23J9/kop4FbxIsu5YvjuexPIqudoEnMEDQ0jO604ELTGyWax3fre+daRs\nYY7fd2bEAJZrXQgesZlHIMwZZMWo76FleQ8tKFMZKDAgkAHUugVDKyKg3AjfGQyM\n3kr7oQkjg5gPNU6LHh+VUuG7+Fzu+tyTondn01m4YRNfiTzP4S4M6s3H1cghhnga\nbKUeGzSUey+VSvo/Ir3N49zn01eeewY6gJMPw9xV/f3ijer83NMuOTGuc3JW1NXp\nbV0KzAECgYEA/mlijzdWM1pwBu8A/Dc51z1rOcIyr/ZAELh5rGUb5FM77if9CynV\nqSfEIxWI3snrIls+/qse1agYgb5yJroVO1BApWoOj2SyGwUzE2ncnF58BG/yES+l\nHxodwQraaZCiz4zC2YOSfV8Muouf20PcGzkOP8CazMyn7IdfbuIiBRECgYEA4MZd\nrhHwEt8Tbn0A260OCAk4c5vOBZvd5rqivfcKGBnGlR0zZKeGkd+Aby2U8S7GpIzm\nL0BbtVJqUEFvITIIm3X9NFZei2xeKCo2TkiEhtsVCAFfGp5Zvc7yjJuHucxWuuuT\n+Mgb3eRCqMzhjh/xTwnukB3i03ppHsjSe+WEjjMCgYBBNIdzR26LeOlvjYBGJG1p\nsi8yPYi6OrYO0wk0WzG74m1gy9T6MH23fh6yE0niOARQ6OwLX5Zmkk+9qS8ep+Db\nM+Vtv/H9ZISVkk6V8jL9zOWiSYLUTs7WWt43ZO230r83zM7/6s333g2oHjMZgpn+\nTDBPvLCwPt/nKocWJ1Uq0QKBgANNhuTe6JsuYfe2qIOR2Gnv0L+KI43bi3gvd+K4\ntZJDFrLsOewZthWApj97+PtOR6b1VxCMroxMiLljLMHdHVlDc5QITN1Zm0yVyjR+\nRkxA/d8fPgmDGCh82P2N74GgagnXGlaGgjpRd1VJpWrUN1SE/ddqSQH4g4DrTIR7\ni+YXAoGAJOJyJC7ERwz7AcfdMdADxonxsK1sRPB9/qBgMrjKPgo+hFcLf19ruoGP\nf6y/rjzGDGjC6h1xjlMEmuaj7jo9bpRPB35lt+0sW5TC0E1kyto6bzA2tBtdKEfJ\nPCdndXdc0ix1dL4ssYXJQYHz6fPlMSl7W5QJew3n7UbBQ+Z6gw8=\n-----END RSA PRIVATE KEY-----"  # noqa
        self.JWT_PUBLIC_KEY = {"alg": "RS512", "e": "AQAB", "kty": "RSA", "n": "32FY2NFy0yXKMp9aFP8E_oF_4czX2dvrJmOxyG_5OepdHVauoiE0WCMI7jzm7uYxF98CZNlMXxE0FKqVPchYBydbqMj-L4GxZqMbgUJ19c4HHLNARN1bTlqaQpRZxY_Fsk_xylNRYIgM5QY0lflguPrAY4uOQhriySJSz-tqs_gwdcTZwPZj80v4qE7ZSw0E-ZPP8Cfbmh6uvuM659c18NIl9o6brOTw9BcHmpCEK4JSS759LpEPZtUd5jmx5IqLwSKuaQJ0_XXjz4PTKinBrWbTyiaAkL30fKpYAn4sztQbyzMqZFe0rec_SlUUkUkwgrbTPpFSnb4dJO3DvVpwYw"}  # noqa


class Production(Default):
    """Production environment configuration."""

    def __init__(self):
        """
        Initialize the production environment configuration.

        Require a secret key to be defined and make logging slightly less
        verbose.
        """
        super().__init__()
        self.DEBUG = False
        self.SECRET_KEY = os.environ['SECRET_KEY']
        self.LOGGING['root']['level'] = 'INFO'
