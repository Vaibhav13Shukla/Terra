# Terra API Lambda — container image (not zip: rasterio/GDAL exceed the
# 250MB zip-deployment limit; see docs/adr/002-processing-runtime.md).
FROM public.ecr.aws/lambda/python:3.11

COPY backend/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY backend/app ${LAMBDA_TASK_ROOT}/app

CMD ["app.api.main.handler"]
