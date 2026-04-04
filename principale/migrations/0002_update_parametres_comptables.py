from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('principale', '0001_initial'),
    ]

    operations = [
        # Pour SQLite, nous allons utiliser une approche spécifique
        # d'abord, créer une nouvelle table avec la structure correcte
        migrations.RunSQL(
            sql="""
            CREATE TABLE "principale_parametrescomptables_new" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                "annee" integer NOT NULL,
                "solde_initial" decimal NOT NULL,
                "compte_courant_initial" decimal NOT NULL,
                "sci_id" integer NULL REFERENCES "principale_sci" ("id") DEFERRABLE INITIALLY DEFERRED
            );
            
            -- Copier les données existantes
            INSERT INTO principale_parametrescomptables_new (annee, solde_initial, compte_courant_initial, sci_id)
            SELECT annee, solde_initial, compte_courant_initial, NULL FROM principale_parametrescomptables;
            
            -- Supprimer l'ancienne table
            DROP TABLE principale_parametrescomptables;
            
            -- Renommer la nouvelle table
            ALTER TABLE principale_parametrescomptables_new RENAME TO principale_parametrescomptables;
            
            -- Créer un index pour la contrainte unique
            CREATE UNIQUE INDEX principale_parametrescomptables_sci_id_annee_idx
            ON principale_parametrescomptables(sci_id, annee)
            WHERE sci_id IS NOT NULL;
            """,
            reverse_sql="""
            -- En cas de rollback, cette partie est plus complexe et dépend de votre structure initiale
            -- Ceci est une simplification
            CREATE TABLE "principale_parametrescomptables_old" (
                "annee" integer NOT NULL PRIMARY KEY,
                "solde_initial" decimal NOT NULL,
                "compte_courant_initial" decimal NOT NULL
            );
            
            INSERT INTO principale_parametrescomptables_old (annee, solde_initial, compte_courant_initial)
            SELECT annee, solde_initial, compte_courant_initial FROM principale_parametrescomptables;
            
            DROP TABLE principale_parametrescomptables;
            
            ALTER TABLE principale_parametrescomptables_old RENAME TO principale_parametrescomptables;
            """
        ),
    ]