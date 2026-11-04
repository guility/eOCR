# Доказательства для полного OCR inference runtime и GPU kernels

**Контекст:** исследовательская заметка к [issue #5](https://github.com/guility/eOCR/issues/5). Термины «инференсный runtime», «модель затрат» и «эталонная аннотация» используются в смысле [GLOSSARY.md](https://github.com/guility/eOCR/blob/main/GLOSSARY.md).
**Срез источников:** 4 ноября 2026 г.
**Метод:** первичные научные работы, официальная документация и исходные репозитории. Утверждения о границах применимости — вывод из перечисленных источников; это не аудит конкретной будущей конфигурации eOCR.

## Короткий вывод

В рассмотренных источниках не нашлась готовая система, которая одновременно доказывает в Lean соответствие всего OCR inference runtime (модель, хост-код, все тензорные операции, GPU kernel source и скомпилированный GPU-код), доказывает tight time- и memory-bounds относительно заданной модели затрат и устанавливает глобальное отсутствие лишних операций и объектов.

Есть полезные, но раздельные компоненты:

- [TorchLean](https://github.com/lean-dojo/TorchLean) задаёт и доказывает свойства нейросетевой модели и графа в Lean, умеет выполнять выбранные операции через GPU/LibTorch, однако прямо классифицирует CUDA, LibTorch, компилятор и драйвер как внешние границы доверия.
- Недавняя работа [о доказательстве CUDA kernels в Lean и VerCors](https://arxiv.org/abs/2610.24548) связывает Float32-семантику Lean с ограниченным переводом CUDA-кода в Lean и отдельно проверяет безопасность потоков; это подтверждение реализуемости отдельных kernels, а не полного runtime.
- [GPUVerify](https://2012.splashcon.org/details/splash-2012-OOPSLA-Research-Papers/13/GPUVerify-a-verifier-for-GPU-kernels) проверяет ограниченные классы ошибок исходного CUDA/OpenCL kernel — data races и barrier divergence.
- [RaCUDA](https://doi.org/10.1145/3639403) даёт доказанные в Coq верхние границы для явных CUDA cost metrics на subset CUDA. Авторы **не** заявляют точное время выполнения на реальном GPU.
- [TensorRight](https://doi.org/10.1145/3704865) проверяет многие tensor graph rewrites для произвольных рангов и размеров, но только в собственном IR и с конкретными ограничениями на операции и числа.

Поэтому строгая цель реалистична только как программа исследований с зафиксированными моделью, версиями и аппаратной конфигурацией, узким набором kernel/операций и явно условными утверждениями. В частности, «tight» и «без лишнего» нельзя заявить до определения модели затрат и критерия оптимальности.

## Что именно нужно доказывать

| Свойство | Что может быть доказано | Что не следует автоматически |
| --- | --- | --- |
| Семантика OCR path | Равенство результата реализации с явной спецификацией для допустимых входов, модели и параметров | Истинность эталонной аннотации или корректность самой спецификации |
| Kernel correctness | Эквивалентность kernel спецификации при оговорённых входных предпосылках и FP-семантике | Корректность CUDA-компиляции и совпадение с машинным кодом |
| Kernel safety | Отсутствие гонок, небезопасного доступа и некорректных барьеров в поддерживаемой модели | Совпадение численного результата со спецификацией |
| Ресурсы | Верхняя граница счётчика выбранных событий/операций в формальной модели | Wall-clock time, расход драйвера/кэширующего allocator или оптимальность |
| «Нет лишних» | Для заданного IR и метрики — отсутствие операций/аллокаций, запрещённых формальным инвариантом | Глобально самый быстрый код или минимум объектов среди всех эквивалентных реализаций |

Доказательство сравнивает программу с формальной спецификацией. Для OCR это оставляет отдельный вопрос о качестве/истинности разметки: Lean может доказать, что проверка корректно сравнила результат с эталонной аннотацией, но не то, что аннотация верна для исходного PDF.

## Существующие варианты

### Lean для модели и графа

TorchLean — самый близкий из найденных Lean-проектов к формализации ML-модели вместе с вычислимой семантикой. В репозитории указаны типизированные тензоры, Lean-граф, проверки форм и численных свойств, а также CUDA-backed исполнение. Но проект прямо говорит, что CUDA kernels, LibTorch, PyTorch, компилятор, драйвер и hardware остаются внешними исполнителями. Его доказательства о модели/графе сами по себе не доказывают соответствие Float-округлений и compiled CUDA execution формальной семантике. Это хороший источник для Lean-спецификации и graph-level proof, не готовое доказательство всего GPU runtime. См. [TorchLean paper](https://arxiv.org/abs/2602.22631), [репозиторий](https://github.com/lean-dojo/TorchLean) и особенно [документ границ доверия](https://github.com/lean-dojo/TorchLean/blob/main/docs/TRUST_BOUNDARIES.md).

Работа [Browne, Lee, Salvi (2026)](https://arxiv.org/abs/2610.24548) показывает более прямую связку Lean с CUDA: ограниченный детерминированный перевод CUDA в Lean проверяет семантическую эквивалентность базовым PyTorch specs над Float32; VerCors отдельно проверяет безопасность параллельного кода. Авторы приводят 30 задач и явно ограничивают доказательство поддерживаемым переводчиком. Трансцендентные функции остаются opaque: перенос доказательства на исполняемый код зависит от совпадения их реализаций. Это свежий preprint/прототип, а не проверенный конвейер компиляции произвольных OCR kernels до GPU ISA.

Официальная [Lean Language Reference](https://lean-lang.org/doc/reference/latest/) описывает минимальный kernel, проверяющий proof terms. Это сильная основа для логических теорем. Но native execution — другой уровень: компилятор генерирует C, далее его собирает native C compiler, а unsafe и FFI-код не проверяются Lean kernel как вычисления реализации. [Документация Lean FFI](https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/) отдельно называет интерфейс unstable и возлагает согласование тела @[extern] с Lean-декларацией на пользователя. Следовательно, доказанная Lean-функция плюс CUDA FFI не доказывают эквивалентность внешнего вызова.

### Проверка GPU kernel source

[GPUVerify](https://2012.splashcon.org/details/splash-2012-OOPSLA-Research-Papers/13/GPUVerify-a-verifier-for-GPU-kernels) задаёт семантику CUDA/OpenCL kernels и сводит анализ массива потоков к последовательному анализу пары символических потоков. Проверяемые свойства — прежде всего меж-/внутригрупповые гонки данных и расхождение на барьерах. [Документация и исходники](https://github.com/mc-imperial/gpuverify) подтверждают область инструмента; успешный отчёт означает отсутствие именно тех классов ошибок, которые поддерживает GPUVerify. Он не доказывает равенство произвольной реализации OCR-оператору, численную погрешность, время или работу compiler/runtime.

### Верхние границы ресурсов

[RaCUDA / miniCUDA](https://doi.org/10.1145/3639403) — наиболее прямой найденный результат по cost semantics для CUDA. В Coq формализованы семантика и soundness quantitative logic; инструмент обрабатывает sizeable subset CUDA и строит символические верхние границы для параметризованных метрик, например memory sectors, shared-memory bank conflicts, divergent warps, шагов модели, а также work/span. [Публичный артефакт](https://github.com/smuller/RaCUDA) содержит Coq scripts и инструмент.

Важное ограничение авторы указывают сами: они не пытаются получить точное время запуска на реальном GPU, поскольку расписание потоков зависит от недоопределённого планировщика и latency hiding. Work/span и счётчики событий полезны как модель анализа, но не являются гарантией конкретного wall-clock времени. Результаты RaCUDA выполнены в Coq; перенос в Lean потребует отдельно доказать/перенести семантику и теоремы, а не просто обернуть существующий инструмент.

### Графовые преобразования тензоров

[ONNX IR specification](https://github.com/onnx/onnx/blob/main/docs/IR.md) определяет computation graph, типы и операторы — это контракт формата, не доказательство всех реализаций ONNX runtime и Execution Providers.

[TensorRight (POPL 2025)](https://doi.org/10.1145/3704865) формализует собственный tensor DSL и автоматически проверяет эквивалентность многих XLA-HLO rewrite rules для произвольных рангов/размеров через reduction unbounded задачи к конечному набору SMT-проверок. В их оценке представлено 121 правило XLA, доказано 115. Это доказательство корректности преобразований, а не корректности всего XLA, сгенерированного CUDA-кода или performance-оптимальности. Ограничения включают отсутствие layout-sensitive reshape/bitcast, неполную поддержку reduction cases и трудности с точностью floating-point выражений. Описание метода прямо говорит об SMT-проверках, поэтому цепочка доверия должна учитывать verifier/solver и корректность реализации frontend; это не Lean kernel-checked proof объекта.

### Проверенные компиляторы и Rust

[CompCert](https://compcert.org/doc/) имеет machine-checked semantic-preservation theorem для CompCert C и целевых CPU ISA (ARM, PowerPC, RISC-V, x86). Он показывает ценность доказанного backend для подходящего языка/target, но его официальный target list не включает CUDA/PTX или GPU execution; поэтому CompCert не закрывает CUDA compilation.

Отдельный актуальный прототип — [Forge](https://github.com/garrick247/forge), язык контрактов с генерацией CUDA C/PTX и SMT discharge. Его собственный [SOUNDNESS.md](https://github.com/garrick247/forge/blob/main/SOUNDNESS.md) прямо уточняет, что это не machine-verified compiler в смысле CompCert: доверяются parser, переводу VC в SMT-LIB, Z3 и code emitter; эмиссия CUDA/PTX проверялась differential/runtime testing, а SASS parity показана для пяти reference kernels. Это полезный пример proof obligations и явного TCB, но не proof-carrying compilation до GPU ISA.

[Aeneas](https://github.com/AeneasVerif/aeneas) переводит subset safe Rust в функциональные модели для Lean, Coq, F*, HOL4. Репозиторий отмечает, что unsafe и concurrency — текущие ограничения/направления расширения. Это может помочь доказать безопасную host-side Rust-логику, но пока не даёт Lean-спецификации исполняемого GPU kernel и не доказывает FFI/backend.

CUDA Execution Providers дополнительно усложняют «полный runtime»: например, [ONNX Runtime](https://onnxruntime.ai/docs/execution-providers/) допускает несколько providers, а его [архитектура](https://onnxruntime.ai/docs/reference/high-level-design.html) исходит из того, что провайдер не всегда исполняет модель целиком. Если eOCR выберет такой путь, придётся проверять graph partition/fallback и каждый provider, а не считать, что весь граф исполняется одним набором GPU kernels.

## Доверенная граница полного утверждения

Для утверждения «реально исполняемый inference runtime соответствует доказанному Lean theorem» потребуются явные мосты между всеми следующими слоями:

1. **Спецификация OCR:** подготовка PDF/изображения, нормализация, токенизация/декодирование, правила постобработки, веса модели и допустимые входы. Теорема гарантирует только спецификацию; provenance аннотаций и модели — отдельное условие.
2. **Импорт модели / graph lowering:** соответствие ONNX/PyTorch модели и её фактического графа Lean-IR. Для каждого operator, атрибута, layout, dtype и shape нужен проверенный импорт или проверяемый сертификат.
3. **Rewrite/optimization passes:** доказательство семантического сохранения каждого прохода, включая fused operations, layout и floating-point порядок. TensorRight покрывает класс graph rewrites, но не автоматически весь production compiler.
4. **Kernel source:** точная численная семантика, индексация, memory layout, синхронизация, races, предпосылки размеров и входов. GPUVerify/VerCors помогают с безопасностью; численное равенство требует отдельного semantic proof.
5. **Сборка GPU-кода:** связь проверенного CUDA source с PTX и далее с целевым native machine code. CUDA использует PTX как виртуальный ISA, а GPU backend/JIT и конкретная архитектура создают ещё одну границу; [документация NVIDIA](https://docs.nvidia.com/cuda/cuda-programming-guide/) описывает эту многоступенчатую модель, но не предоставляет proof of compiler correctness.
6. **Runtime и библиотеки:** host compiler, CUDA runtime/driver, allocator, streams, библиотечные kernels (например, cuBLAS/cuDNN/LibTorch/TensorRT) и fallback CPU paths.
7. **Hardware и FP:** выбранная архитектура, memory consistency, порядок редукции, FMA/rounding, FTZ и поведение transcendental operations. «Эквивалентно над ℝ» недостаточно для битового совпадения FP32.
8. **Доверенная база доказательства:** Lean kernel, импортированные axioms, unsafe, FFI, SMT solver/proof checker и любые executable replacements. Для FFI требуется отдельное доказательство соответствия native body модели.

Практически доказуемое утверждение должно перечислить всё, что остаётся предпосылкой, и фиксировать версии runtime/compiler, device capability, dtype/precision flags, model/weight hash, входные формы и deterministic settings.

## Tight bounds и «лишние» операции

Нужно сначала определить модель затрат. Возможный вектор метрик для конкретного OCR path:

**C = (F_dtype/op, B_global-read, B_global-write, B_shared, N_launch, A_bytes, M_peak-live, S_sync, D_warp)**

где A_bytes считает создание/освобождение объектов или буферов, M_peak-live — максимум одновременно живых байтов, а N_launch — запусков GPU kernels. Host-side объекты, pinned memory, allocator cache/reservation и device allocations следует считать раздельно, если продуктовый смысл требует их включить.

Затем можно доказать **верхние границы** для каждой метрики относительно формальной семантики операций, как делает RaCUDA для subset CUDA. Чтобы назвать границу *tight*, нужен подходящий доказанный lower bound в той же модели и на том же наборе предпосылок; например, по обязательным чтениям входа/весов или нижней границе пикового live set. Равенство upper/lower доказывает tightness только для указанного cost model.

Перевести эти счётчики во wall-clock можно только через отдельную аппаратно-зависимую модель (архитектура, частоты, cache, concurrency, scheduler, allocation/launch overhead). Измерения могут калибровать модель и показывать корреляцию, но сами не превращают её в доказанную границу времени.

Фраза «нет лишних операций/объектов» также требует формального смысла. Локально можно доказать, что в определённом IR нет мёртвых узлов, что fusion не материализует промежуточный тензор или что liveness/ownership не создаёт дополнительных аллокаций. Глобальное «самый быстрый/минимальный среди всех эквивалентных программ» не следует из correctness proof или cost upper bound; необходимо ограничить язык кандидатов и аппаратную модель, определить скалярную цель/порядок метрик и доказать нижнюю границу. Без этих условий утверждение о глобальной оптимальности некорректно.

## Рекомендуемая постановка достижимой цели

Сильное, но проверяемое утверждение можно сузить так:

> Для зафиксированных OCR-модели и весов, версий runtime/compiler, dtype, входных размеров и одной GPU-архитектуры Lean доказывает соответствие формализованной модели инференса указанным kernel/host path; отдельные анализаторы доказывают свойства safety для поддерживаемого CUDA subset; количественные теоремы дают верхние границы по явно названным операциям, передачам и пиковым live bytes. Корректность компиляции, внешних библиотек и аппаратного исполнения перечисляется как доверенная предпосылка до появления проверенного моста к binary/device.

Порядок работ:

1. Зафиксировать реальный OCR path и перечислить, что означает «полный» для его host, preprocessing, model, postprocessing и output.
2. Задать Lean-спецификацию форм/численных форматов и end-to-end observable result; отдельно определить отношение к эталонной аннотации.
3. Построить графовый импорт/IR с проверяемым correspondence. TorchLean полезен как исследовательская база, но надо сверить, покрывает ли он конкретные операции, модель и deployment runtime.
4. Для каждого GPU kernel доказать kernel-to-spec численную эквивалентность и memory/thread safety. Указывать, какой именно переводчик/анализатор используется и что он не покрывает.
5. Задать ресурсную семантику, включив host allocations, GPU allocations, copies и launches. Начать с верхних границ метрик, которые можно связать с source; оформлять нижние границы и tightness отдельно.
6. До доказанного source-to-binary/device моста называть результат условной гарантией о проверенной модели/source, а не доказательством полного реально исполняемого runtime.

**Итоговая оценка:** доказать спецификацию и выбранные операции/ядра возможно; доказать весь inference runtime условно и послойно возможно при узком deployment contract. Tight wall-clock и глобальная минимальность не следуют из известных Lean/Rust/GPU инструментов. Самые реалистичные ближайшие гарантии — end-to-end model semantics плюс проверяемый набор kernel contracts/safety и доказанные bounds по явной, архитектурно ограниченной векторной модели затрат.

## Основные первичные источники

- [TorchLean: Formalizing Neural Networks in Lean (2026 preprint)](https://arxiv.org/abs/2602.22631); [source repository](https://github.com/lean-dojo/TorchLean); [trust boundaries](https://github.com/lean-dojo/TorchLean/blob/main/docs/TRUST_BOUNDARIES.md)
- [Proving LLM-Generated GPU Kernels Correct and Safe: Floating-Point Verification in Lean and VerCors (2026 preprint)](https://arxiv.org/abs/2610.24548)
- [GPUVerify: A Verifier for GPU Kernels (OOPSLA 2012)](https://2012.splashcon.org/details/splash-2012-OOPSLA-Research-Papers/13/GPUVerify-a-verifier-for-GPU-kernels); [source and usage docs](https://github.com/mc-imperial/gpuverify)
- [Modeling and Analyzing Evaluation Cost of CUDA Kernels (POPL 2021)](https://doi.org/10.1145/3434306); extended [TOPC 2024 paper](https://doi.org/10.1145/3639403); [RaCUDA Coq artifact](https://github.com/smuller/RaCUDA)
- [TensorRight: Automated Verification of Tensor Graph Rewrites (POPL 2025)](https://doi.org/10.1145/3704865); [artifact](https://github.com/ADAPT-uiuc/TensorRight)
- [ONNX IR specification](https://github.com/onnx/onnx/blob/main/docs/IR.md); [ONNX Runtime Execution Providers](https://onnxruntime.ai/docs/execution-providers/)
- [CompCert formally verified compiler docs](https://compcert.org/doc/); [Forge and its explicit TCB](https://github.com/garrick247/forge/blob/main/SOUNDNESS.md)
- [Aeneas Rust-to-Lean verification toolchain](https://github.com/AeneasVerif/aeneas)
- [Lean reference: compilation and kernel](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/); [Lean FFI](https://lean-lang.org/doc/reference/latest/Run-Time-Code/Foreign-Function-Interface/)
- [NVIDIA CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/)
