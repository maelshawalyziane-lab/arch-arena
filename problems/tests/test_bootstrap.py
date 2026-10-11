"""Amorçage d'une installation neuve (`manage.py bootstrap`).

C'est la commande que la production exécute au premier démarrage : si elle échoue, le site
se déploie sans compte et sans catalogue. Ces tests la verrouillent — compte unique créé,
mot de passe pris dans l'environnement, idempotence.
"""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import TestCase

from problems.models import Problem


class BootstrapTests(TestCase):
    """La commande d'amorçage, sans le corpus (trop lourd pour une suite de tests)."""

    def test_creates_the_single_account(self):
        call_command("bootstrap", skip_corpus=True, password="mot-de-passe-de-test", verbosity=0)
        User = get_user_model()
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertIsNotNone(authenticate(username="admin", password="mot-de-passe-de-test"))

    def test_is_idempotent_and_keeps_the_password(self):
        call_command("bootstrap", skip_corpus=True, password="premier-mdp", verbosity=0)
        call_command("bootstrap", skip_corpus=True, password="second-mdp", verbosity=0)
        User = get_user_model()
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password("premier-mdp"), "le mot de passe ne doit pas changer")

    def test_skip_corpus_leaves_the_catalogue_alone(self):
        call_command("bootstrap", skip_corpus=True, password="mot-de-passe-de-test", verbosity=0)
        self.assertEqual(Problem.objects.count(), 0)

    def test_password_comes_from_the_environment(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"ARCH_ADMIN_PASSWORD": "depuis-environnement"}):
            call_command("bootstrap", skip_corpus=True, verbosity=0)
        self.assertIsNotNone(authenticate(username="admin", password="depuis-environnement"))
