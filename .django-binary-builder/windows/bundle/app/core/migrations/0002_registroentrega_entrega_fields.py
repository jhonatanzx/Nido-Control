from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroentrega',
            name='apoderado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.apoderado'),
        ),
        migrations.AddField(
            model_name='registroentrega',
            name='documento_verificado',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
