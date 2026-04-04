# Créez un nouveau fichier utils.py dans votre application

import csv
import decimal
from datetime import datetime
from django.db import transaction
from .models import Bien, Locataire, Transaction, TypeTransaction, ImportFile

# Définition des en-têtes attendus pour chaque type d'import
HEADERS = {
    'BIEN': ['type_bien', 'adresse', 'code_postal', 'ville', 'loyer_mensuel', 'numero'],
    'LOCATAIRE': ['bien_id', 'nom', 'prenom', 'telephone', 'email', 'date_entree', 'date_sortie', 
                 'caution_versee', 'montant_caution', 'date_versement_caution', 'date_restitution_caution'],
    'TRANSACTION': ['type_transaction_id', 'bien_id', 'locataire_id', 'sci', 'montant', 'date', 
                   'mois_concerne', 'description']
}

# Types de données attendus pour chaque champ
FIELD_TYPES = {
    # Bien
    'type_bien': {'type': 'choice', 'choices': ['APPARTEMENT', 'MAISON']},
    'adresse': {'type': 'string', 'max_length': 255},
    'code_postal': {'type': 'string', 'max_length': 10},
    'ville': {'type': 'string', 'max_length': 100},
    'loyer_mensuel': {'type': 'decimal'},
    'numero': {'type': 'string', 'max_length': 50, 'required': False},
    
    # Locataire
    'bien_id': {'type': 'integer', 'model': Bien},
    'nom': {'type': 'string', 'max_length': 100},
    'prenom': {'type': 'string', 'max_length': 100},
    'telephone': {'type': 'string', 'max_length': 20, 'required': False},
    'email': {'type': 'email', 'required': False},
    'date_entree': {'type': 'date'},
    'date_sortie': {'type': 'date', 'required': False},
    'caution_versee': {'type': 'boolean'},
    'montant_caution': {'type': 'decimal', 'required': False},
    'date_versement_caution': {'type': 'date', 'required': False},
    'date_restitution_caution': {'type': 'date', 'required': False},
    
    # Transaction
    'type_transaction_id': {'type': 'integer', 'model': TypeTransaction},
    'locataire_id': {'type': 'integer', 'model': Locataire, 'required': False},
    'sci': {'type': 'boolean'},
    'montant': {'type': 'decimal'},
    'date': {'type': 'date'},
    'mois_concerne': {'type': 'date', 'required': False},
    'description': {'type': 'string', 'required': False}
}

def validate_csv_file(import_file):
    """
    Valide le fichier CSV téléchargé et renvoie un dictionnaire avec les résultats de validation
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'rows': [],
        'headers': [],
        'total_rows': 0,
        'valid_rows': 0
    }
    
    expected_headers = HEADERS[import_file.type_import]
    
    try:
        # Ouvrir le fichier CSV et vérifier le format
        with open(import_file.file.path, 'r', encoding='utf-8-sig') as f:
            csv_reader = csv.reader(f, delimiter=';')
            
            # Lire la première ligne (en-têtes)
            try:
                headers = next(csv_reader)
            except StopIteration:
                results['valid'] = False
                results['errors'].append("Le fichier est vide ou mal formaté.")
                return results
            
            # Vérifier que les en-têtes correspondent aux attendus
            headers = [h.strip().lower() for h in headers]
            results['headers'] = headers
            
            missing_headers = [h for h in expected_headers if h not in headers]
            if missing_headers:
                results['valid'] = False
                results['errors'].append(f"En-têtes manquants: {', '.join(missing_headers)}")
                return results
            
            # Traiter chaque ligne
            row_number = 1  # Commencer à 1 pour compter après les en-têtes
            for row in csv_reader:
                row_number += 1
                row_data = {}
                row_errors = []
                
                # Vérifier si la ligne a le bon nombre de colonnes
                if len(row) != len(headers):
                    row_errors.append(f"Le nombre de colonnes ({len(row)}) ne correspond pas aux en-têtes ({len(headers)})")
                    continue
                
                # Vérifier chaque valeur
                for i, header in enumerate(headers):
                    if header not in expected_headers:
                        continue  # Ignorer les colonnes supplémentaires
                    
                    value = row[i].strip()
                    field_spec = FIELD_TYPES.get(header, {'type': 'string'})
                    
                    # Vérifier si la valeur est requise
                    if not field_spec.get('required', True) and not value:
                        row_data[header] = None
                        continue
                    
                    # Vérifier selon le type attendu
                    try:
                        if field_spec['type'] == 'integer':
                            if value:
                                val = int(value)
                                
                                # Vérifier si la référence existe
                                if 'model' in field_spec and not field_spec.get('required', True) == False:
                                    model = field_spec['model']
                                    try:
                                        obj = model.objects.get(pk=val)
                                        row_data[header] = val
                                    except model.DoesNotExist:
                                        row_errors.append(f"La référence {header}={val} n'existe pas")
                                else:
                                    row_data[header] = val
                            else:
                                if field_spec.get('required', True):
                                    row_errors.append(f"La valeur pour {header} est requise")
                                else:
                                    row_data[header] = None
                        
                        elif field_spec['type'] == 'decimal':
                            if value:
                                # Remplacer la virgule par un point pour la conversion
                                value = value.replace(',', '.')
                                val = decimal.Decimal(value)
                                row_data[header] = val
                            else:
                                if field_spec.get('required', True):
                                    row_errors.append(f"La valeur pour {header} est requise")
                                else:
                                    row_data[header] = None
                        
                        elif field_spec['type'] == 'date':
                            if value:
                                try:
                                    # Essayer différents formats de date
                                    formats = ['%d/%m/%Y', '%Y-%m-%d']
                                    date_value = None
                                    
                                    for fmt in formats:
                                        try:
                                            date_value = datetime.strptime(value, fmt).date()
                                            break
                                        except ValueError:
                                            continue
                                    
                                    if date_value:
                                        row_data[header] = date_value
                                    else:
                                        row_errors.append(f"Format de date invalide pour {header}: {value}")
                                except Exception as e:
                                    row_errors.append(f"Format de date invalide pour {header}: {value}")
                            else:
                                if field_spec.get('required', True):
                                    row_errors.append(f"La valeur pour {header} est requise")
                                else:
                                    row_data[header] = None
                        
                        elif field_spec['type'] == 'boolean':
                            if value.lower() in ['oui', 'yes', 'vrai', 'true', '1']:
                                row_data[header] = True
                            elif value.lower() in ['non', 'no', 'faux', 'false', '0', '']:
                                row_data[header] = False
                            else:
                                row_errors.append(f"Valeur booléenne invalide pour {header}: {value}")
                        
                        elif field_spec['type'] == 'choice':
                            if value.upper() in field_spec['choices']:
                                row_data[header] = value.upper()
                            else:
                                row_errors.append(f"Valeur non autorisée pour {header}: {value}. Valeurs possibles: {', '.join(field_spec['choices'])}")
                        
                        elif field_spec['type'] == 'email':
                            if value:
                                # Vérification simplifiée d'une adresse email
                                if '@' in value and '.' in value:
                                    row_data[header] = value
                                else:
                                    row_errors.append(f"Adresse email invalide pour {header}: {value}")
                            else:
                                if field_spec.get('required', True):
                                    row_errors.append(f"La valeur pour {header} est requise")
                                else:
                                    row_data[header] = None
                        
                        else:  # string par défaut
                            max_length = field_spec.get('max_length', 0)
                            if max_length and len(value) > max_length:
                                row_errors.append(f"La valeur pour {header} dépasse la longueur maximale ({max_length}): {value}")
                            row_data[header] = value
                    
                    except (ValueError, decimal.InvalidOperation) as e:
                        row_errors.append(f"Valeur invalide pour {header}: {value}")
                
                # Ajouter la ligne à la liste des résultats
                row_result = {
                    'number': row_number,
                    'data': row_data,
                    'errors': row_errors,
                    'valid': len(row_errors) == 0
                }
                
                results['rows'].append(row_result)
                if row_result['valid']:
                    results['valid_rows'] += 1
                else:
                    results['valid'] = False  # Au moins une ligne a des erreurs
            
            results['total_rows'] = row_number - 1  # Soustraire la ligne d'en-têtes
            
            # Mettre à jour le nombre de lignes dans le modèle
            import_file.row_count = results['total_rows']
            import_file.save()
            
            return results
    
    except Exception as e:
        results['valid'] = False
        results['errors'].append(f"Erreur lors de la lecture du fichier: {str(e)}")
        
        # Mettre à jour le statut du fichier en cas d'erreur
        import_file.status = 'ERROR'
        import_file.error_message = str(e)
        import_file.save()
        
        return results

@transaction.atomic
def import_data(import_file):
    """
    Importe les données du fichier CSV dans la base de données
    """
    try:
        # Valider à nouveau le fichier
        results = validate_csv_file(import_file)
        
        if not results['valid']:
            import_file.status = 'ERROR'
            import_file.error_message = "Le fichier contient des erreurs et ne peut pas être importé."
            import_file.save()
            return False, "Le fichier contient des erreurs et ne peut pas être importé."
        
        # Commencer une transaction pour pouvoir annuler en cas d'erreur
        with transaction.atomic():
            # Importer selon le type
            if import_file.type_import == 'BIEN':
                for row in results['rows']:
                    if row['valid']:
                        data = row['data']
                        bien = Bien(
                            type_bien=data['type_bien'],
                            adresse=data['adresse'],
                            code_postal=data['code_postal'],
                            ville=data['ville'],
                            loyer_mensuel=data['loyer_mensuel'],
                            numero=data.get('numero')
                        )
                        bien.save()
            
            elif import_file.type_import == 'LOCATAIRE':
                for row in results['rows']:
                    if row['valid']:
                        data = row['data']
                        bien = None
                        if data.get('bien_id'):
                            bien = Bien.objects.get(pk=data['bien_id'])
                        
                        locataire = Locataire(
                            bien=bien,
                            nom=data['nom'],
                            prenom=data['prenom'],
                            telephone=data.get('telephone'),
                            email=data.get('email'),
                            date_entree=data['date_entree'],
                            date_sortie=data.get('date_sortie'),
                            caution_versee=data['caution_versee'],
                            montant_caution=data.get('montant_caution'),
                            date_versement_caution=data.get('date_versement_caution'),
                            date_restitution_caution=data.get('date_restitution_caution')
                        )
                        locataire.save()
            
            elif import_file.type_import == 'TRANSACTION':
                for row in results['rows']:
                    if row['valid']:
                        data = row['data']
                        
                        type_transaction = TypeTransaction.objects.get(pk=data['type_transaction_id'])
                        
                        bien = None
                        if data.get('bien_id'):
                            bien = Bien.objects.get(pk=data['bien_id'])
                        
                        locataire = None
                        if data.get('locataire_id'):
                            locataire = Locataire.objects.get(pk=data['locataire_id'])
                        
                        transaction = Transaction(
                            type_transaction=type_transaction,
                            bien=bien,
                            locataire=locataire,
                            sci=data['sci'],
                            montant=data['montant'],
                            date=data['date'],
                            mois_concerne=data.get('mois_concerne', data['date']),
                            description=data.get('description')
                        )
                        transaction.save()
            
            # Mettre à jour le statut
            import_file.status = 'IMPORTED'
            import_file.save()
            
            return True, f"{results['valid_rows']} lignes importées avec succès."
    
    except Exception as e:
        import_file.status = 'ERROR'
        import_file.error_message = str(e)
        import_file.save()
        return False, f"Erreur lors de l'import: {str(e)}"