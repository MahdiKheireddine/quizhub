from django.db import migrations
from django.utils.text import slugify


CATEGORIES = [
    ("Programming", "💻", "Code, frameworks, languages", 10),
    ("Science",     "🔬", "Physics, chemistry, biology", 20),
    ("Math",        "🔢", "Numbers, logic, geometry", 30),
    ("History",     "📜", "Events, eras, people", 40),
    ("Geography",   "🌍", "Countries, capitals, places", 50),
    ("Languages",   "🗣️", "Grammar, vocabulary, idioms", 60),
    ("Arts",        "🎨", "Music, painting, literature", 70),
    ("Sports",      "⚽", "Games, athletes, rules", 80),
    ("Pop culture", "🎬", "Movies, music, TV", 90),
    ("General",     "🧠", "Trivia and everything else", 100),
]


def seed(apps, schema_editor):
    Category = apps.get_model("quizzes", "Category")
    for name, icon, desc, order in CATEGORIES:
        Category.objects.update_or_create(
            slug=slugify(name),
            defaults={"name": name, "icon": icon, "description": desc, "order": order},
        )


def unseed(apps, schema_editor):
    Category = apps.get_model("quizzes", "Category")
    Category.objects.filter(slug__in=[slugify(n) for n, *_ in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0003_category_tag_quiz_category_quiz_tags"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
