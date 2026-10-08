#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime
uv export --locked --no-dev --no-emit-project --output-file .runtime/requirements.txt
rm -rf .runtime/package
mkdir -p .runtime/package/backend .runtime/package/web/cli
cp cli/snaptask.py .runtime/package/web/cli/snaptask.py
aws cloudformation deploy --stack-name snaptask-certificate --template-file deploy/certificate.yaml --region us-east-1 --no-fail-on-empty-changeset
snaptask_certificate=$(aws cloudformation describe-stacks --stack-name snaptask-certificate --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='CertificateArn'].OutputValue" --output text)
aws cloudformation deploy --stack-name snaptask-auth --template-file deploy/auth.yaml --region us-east-1 --no-fail-on-empty-changeset
snaptask_client=$(aws cloudformation describe-stacks --stack-name snaptask-auth --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" --output text)
cp backend/*.py .runtime/package/backend/
cp -R web/. .runtime/package/web/
uv pip install --python 3.13 --target .runtime/package --python-version 3.13 --python-platform x86_64-manylinux2014 --only-binary :all: --no-deps --require-hashes -r .runtime/requirements.txt
sam deploy --template-file template.yaml --stack-name snaptask --region eu-west-1 --resolve-s3 --capabilities CAPABILITY_IAM --parameter-overrides "AuthClientId=$snaptask_client" --no-confirm-changeset --no-fail-on-empty-changeset
snaptask_origin=$(aws cloudformation describe-stacks --stack-name snaptask --region eu-west-1 --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" --output text)
snaptask_origin=${snaptask_origin#https://}
snaptask_origin=${snaptask_origin%/}
aws cloudformation deploy --stack-name snaptask-domain --template-file deploy/domain.yaml --region us-east-1 --parameter-overrides "LambdaFunctionUrlDomain=$snaptask_origin" "CertificateArn=$snaptask_certificate" --no-fail-on-empty-changeset
