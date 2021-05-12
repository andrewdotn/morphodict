from argparse import ArgumentParser

from django.core.management import BaseCommand

from CreeDictionary.DatabaseManager.test_db_builder import build_test_xml


class Command(BaseCommand):
    help = """Build test database xml

    The test database XML is generated by extracting definitions from the real
    dictionary that are related to things listed in `res/test_db_words.txt`.
    """

    def add_arguments(self, parser: ArgumentParser):
        pass

    def handle(self, *args, **options):
        build_test_xml()
