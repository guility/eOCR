# Проверка GPU из Docker dev-контейнера на Windows/WSL2

Контекст: [GitHub issue #3](https://github.com/guility/eOCR/issues/3). Проверено 4 ноября 2026 года.

## Вывод

Текущий Docker Desktop действительно передаёт RTX 5090 в Linux-контейнер. Одноразовый официальный CUDA-контейнер увидел NVIDIA GeForce RTX 5090 и 32 607 MiB памяти; проверка прошла с обычным параметром --gpus all. Это подтверждает доступ к устройству и NVML из контейнера. Проверка не запускала CUDA kernel и сама по себе не доказывает работоспособность конкретного OCR/inference runtime.

## Подтверждённое окружение

- Активный Docker context: desktop-linux; Docker Client и Server: 29.9.2; сервер работает с Linux engine x86_64.
- wsl --version: WSL 3.0.3.0, kernel 6.1.21.1.
- В Docker зарегистрирован runtime nvidia (default runtime — runc).
- На Windows nvidia-smi показывает NVIDIA GeForce RTX 5090, driver 610.88, память 32607 MiB.
- Docker Desktop документирует передачу GPU в Linux-контейнеры на Windows через WSL 2 backend и параметр --gpus; prerequisites включают актуальные Windows/NVIDIA drivers и WSL kernel. [Docker Desktop: GPU support](https://docs.docker.com/desktop/features/gpu/)

## Воспроизводимая безопасная проверка

Запустить из PowerShell или терминала интегрированного WSL-дистрибутива, подключённого к Docker Desktop:

    docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi

Команда выполнена успешно. Контейнер вывел:

    NVIDIA-SMI 610.57.01  KMD Version: 610.88  CUDA UMD Version: 13.3
    GPU 0: NVIDIA GeForce RTX 5090
    32607 MiB

Параметр --rm удалил временный контейнер после завершения. Образ отсутствовал локально и был загружен из Docker Hub; pull завершился digest sha256:e778509d37d66475120929671500377524f7278478ba08131b07ef3ffcc0dce0. Образ остался в локальном Docker cache. Настройки Docker/Windows/WSL не менялись, системные компоненты не устанавливались.

Docker описывает такой GPU probe через docker run --rm --gpus all … nvidia-smi; NVIDIA Container Toolkit приводит соответствующий sample workload. CUDA-образы автоматически выставляют нужные NVIDIA capabilities. [Docker Engine: GPU access](https://docs.docker.com/engine/containers/gpu/), [NVIDIA Container Toolkit: sample workload](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html)

## Совместимость образа и GPU

- RTX 5090 относится к Blackwell. Матрица NVIDIA указывает CUDA 12.8 как первую версию CUDA с поддержкой Blackwell; CUDA 12.8 release notes включают поддержку архитектур Blackwell SM_100, SM_101 и SM_120. [NVIDIA CUDA/architecture matrix](https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html), [CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/)
- Для CUDA Toolkit 12.8 GA таблица NVIDIA указывает Windows driver >=570.65; наблюдаемый Windows driver 610.88 выше этого минимума. Совместимость дополнительно подтверждена запуском контейнера.
- nvidia/cuda:12.8.0-base-ubuntu24.04 — опубликованный NVIDIA образ для linux/amd64; его tag и digest доступны на Docker Hub. Вариант base содержит минимальный CUDA runtime (cudart). Этого достаточно для данной проверки GPU visibility; приложениям с CUDA libraries обычно нужен runtime-образ, а сборке CUDA-кода — devel-образ, либо подходящий официальный образ фреймворка. [NVIDIA CUDA image tags](https://hub.docker.com/layers/nvidia/cuda/12.8.0-base-ubuntu24.04/images/sha256-c7890174d7180c01bac52d3f69e052b10e1332efbd3e322a11bb83400c990e2d?tab=layers), [NVIDIA CUDA container-image guide](https://gitlab.com/nvidia/container-images/cuda/-/blob/master/doc/README.md)
- В контейнере nvidia-smi показывает CUDA UMD 13.3; это версия/возможность драйвера, сообщаемая nvidia-smi, а не версия CUDA toolkit внутри образа (образ — CUDA 12.8.0). NVIDIA описывает это различие в своей матрице драйверов и CUDA. [NVIDIA CUDA/architecture matrix](https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html)

## Практический путь для dev-контейнера

Использовать Docker Desktop с WSL 2 backend и текущим desktop-linux context; запускать контейнеры с --gpus all. Отдельная настройка runtime не потребовалась: установленный Desktop engine уже зарегистрировал nvidia, а проверка с минимальной командой прошла. Версию отдельно установленного NVIDIA Container Toolkit из Docker Desktop не извлекали.

NVIDIA указывает, что в WSL нужен Windows NVIDIA driver; Linux display driver устанавливать в WSL не следует. Текущее руководство NVIDIA перечисляет для Docker на WSL Container Toolkit v2.6.0 и libnvidia-container CLI 1.5.1+ и явно отмечает поддержку Docker Desktop; фактическую встроенную версию на хосте отдельно не извлекали, но GPU probe прошёл. Docker рекомендует минимум WSL 2.1.5 для Docker Desktop; наблюдаемая версия WSL — 3.0.3.0. [NVIDIA CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html), [Docker Desktop WSL 2 backend](https://docs.docker.com/desktop/features/wsl/)

Для окончательной проверки обязательного OCR inference runtime следующим шагом запустить минимальный CUDA workload или smoke check самого фреймворка внутри dev-образа. nvidia-smi — проверка видимости устройства и драйверного интерфейса, а не тест вычислений CUDA. WSL имеет ограничения NVML/nvidia-smi, поэтому отдельные показатели и запросы могут быть неполными. [NVIDIA CUDA on WSL: limitations](https://docs.nvidia.com/cuda/wsl-user-guide/index.html#features-not-yet-supported)
