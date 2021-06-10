# Generated by Django 3.2.3 on 2021-06-10 22:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DictionarySource",
            fields=[
                (
                    "abbrv",
                    models.CharField(max_length=8, primary_key=True, serialize=False),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="What is the primary title of the dictionary source?",
                        max_length=256,
                    ),
                ),
                (
                    "author",
                    models.CharField(
                        blank=True,
                        help_text="Separate multiple authors with commas. See also: editor",
                        max_length=512,
                    ),
                ),
                (
                    "editor",
                    models.CharField(
                        blank=True,
                        help_text="Who edited or compiled this volume? Separate multiple editors with commas.",
                        max_length=512,
                    ),
                ),
                (
                    "year",
                    models.IntegerField(
                        blank=True,
                        help_text="What year was this dictionary published?",
                        null=True,
                    ),
                ),
                (
                    "publisher",
                    models.CharField(
                        blank=True, help_text="What was the publisher?", max_length=128
                    ),
                ),
                (
                    "city",
                    models.CharField(
                        blank=True,
                        help_text="What is the city of the publisher?",
                        max_length=64,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Wordform",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=40)),
                ("analysis", models.JSONField(null=True)),
                (
                    "paradigm",
                    models.CharField(
                        default=None,
                        help_text="If provided, this is the name of a static paradigm that this wordform belongs to. This name should match the filename in res/layouts/static/ WITHOUT the file extension.",
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    "is_lemma",
                    models.BooleanField(
                        default=False,
                        help_text="The wordform is chosen as lemma. This field defaults to true if according to fst the wordform is not analyzable or it's ambiguous",
                    ),
                ),
                ("slug", models.CharField(max_length=50)),
                ("linguist_info_stem", models.CharField(blank=True, max_length=128)),
                (
                    "linguist_info_pos",
                    models.CharField(
                        help_text="Inflectional category directly from source xml file",
                        max_length=10,
                    ),
                ),
                (
                    "lemma",
                    models.ForeignKey(
                        help_text="The identified lemma of this wordform. Defaults to self",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inflections",
                        to="lexicon.wordform",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TargetLanguageKeyword",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("text", models.CharField(max_length=20)),
                (
                    "lemma",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="english_keyword",
                        to="lexicon.wordform",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Definition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.CharField(max_length=200)),
                (
                    "auto_translation_source",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="lexicon.definition",
                    ),
                ),
                ("citations", models.ManyToManyField(to="lexicon.DictionarySource")),
                (
                    "wordform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="definitions",
                        to="lexicon.wordform",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="wordform",
            index=models.Index(
                fields=["analysis"], name="lexicon_wor_analysi_971805_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="wordform",
            index=models.Index(fields=["text"], name="lexicon_wor_text_f6cec4_idx"),
        ),
        migrations.AddIndex(
            model_name="wordform",
            index=models.Index(
                fields=["is_lemma", "text"], name="lexicon_wor_is_lemm_916282_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="targetlanguagekeyword",
            index=models.Index(fields=["text"], name="lexicon_tar_text_69f04a_idx"),
        ),
    ]
