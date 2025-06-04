#!/bin/bash

# Import environment variables
source "$(dirname "$0")/../../environment.sh" # Assicurati che TARGET_TAG sia definito qui

# Verifica se la variabile TARGET_TAG è impostata
if [ -z "$TARGET_TAG" ]; then
  echo "Error: TARGET_TAG is not set. Please define it in environment.sh or directly."
  exit 1
fi

echo "Creating/updating firewall rule 'allow-prometheus-ui' for target tag '$TARGET_TAG' to allow tcp on ports 9090 and 9255..."

# Prima prova ad aggiornare la regola se esiste, altrimenti creala.
# O, più semplicemente per uno script, cancella e ricrea (se l'idempotenza non è strettamente necessaria in questo modo)
# Per semplicità, qui usiamo create, che fallirà se la regola esiste già con lo stesso nome.
# Potresti voler aggiungere 'gcloud compute firewall-rules delete allow-prometheus-ui --quiet' prima se vuoi che lo script sia rieseguibile.

gcloud compute firewall-rules delete allow-prometheus-ui --quiet

gcloud compute firewall-rules create allow-prometheus-ui \
    --network=default \
    --allow tcp:9090,tcp:9255 \
    --source-ranges="0.0.0.0/0" \
    --target-tags="$TARGET_TAG" \
    --description="Allow TCP traffic to Prometheus UI (9090) and Stackdriver Exporter (9255)"

# Controlla l'esito del comando
if [ $? -eq 0 ]; then
  echo "Firewall rule 'allow-prometheus-ui' created/updated successfully."
else
  echo "Error creating/updating firewall rule 'allow-prometheus-ui'."
  echo "This might be because the rule already exists with different settings or another issue occurred."
  echo "Consider using 'gcloud compute firewall-rules update allow-prometheus-ui --allow=tcp:9090,tcp:9255' if the rule already exists."
fi