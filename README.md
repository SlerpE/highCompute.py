# highCompute.py

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)  

A single Python file that connects via the OpenAI Chat Completions API, giving you something akin to OpenAI High Compute at home. **Any** models are compatible. Using dynamic programming methods, computational capacity is increased by tens or even hundreds of times for both reasoning and non-reasoning models, significantly improving answer quality and the ability to solve extremely complex tasks for LLMs.  

This is a simple Gradio-based web application providing an interface for interacting with a locally hosted Large Language Model (LLM). The key feature is the ability to select a "Computation Level," which determines the strategy for processing user queries—ranging from direct responses to multi-level task decomposition for obtaining more structured and comprehensive answers to complex queries.  

![image](https://github.com/user-attachments/assets/8886405d-9a49-41ca-89d1-900fdc136d8d)  

The application connects to your specified LLM API endpoint, compatible with the OpenAI Chat Completions API format.  

## 🌟 Key Features  

*   **Local LLM Integration:** Works with your own LLM server (e.g., llama.cpp, Ollama, LM Studio, vLLM with an OpenAI-compatible endpoint).  
*   **Compute Levels:**  
    *   **Low:** Direct query to the LLM for a quick response. Generates N tokens.  
    *   **Medium:** Single-level task decomposition into subtasks, solving them, and synthesizing the answer. Suitable for moderately complex queries. The number of generated tokens roughly squares compared to Low compute. Generates N² tokens.  
    *   **High:** Two-level task decomposition (stages → steps), solving individual steps, synthesizing stage results, and generating a final comprehensive answer. Designed for highly complex and multi-component tasks. The number of generated tokens roughly cubes compared to Low compute. Generates N³ tokens. 

## ⚙️ How It Works: Computation Levels  

The core idea is that for complex tasks, a simple direct query to the LLM may not yield optimal results. Decomposition allows breaking down a complex problem into smaller, manageable parts, solving them individually, and then combining the results.  

1.  **Low:**  
    *   `User Query` → `LLM (single call)` → `Response`  
    *   The fastest mode, suitable for simple questions or when a quick response is needed. Essentially, this is the standard chat mode.  

2.  **Medium:**  
    *   `User Query` → `LLM (decomposition request)` → `List of subtasks`  
    *   *For each subtask:* `Subtask + Context` → `LLM (subtask solution)` → `Subtask result`  
    *   `All subtask results + Original query` → `LLM (final synthesis)` → `Final answer`  
    *   Uses multiple LLM calls. Decomposition and synthesis requests use a lower `temperature` for greater predictability.  

3.  **High:**  
    *   `User Query` → `LLM (Level 1 decomposition)` → `List of stages (L1)`  
    *   *For each L1 stage:*  
        *   `L1 Stage + Context` → `LLM (Level 2 decomposition)` → `List of steps (L2)`  
        *   *If L2 decomposition is not needed:* `L1 Stage + Context` → `LLM (direct L1 stage solution)` → `L1 Stage result`  
        *   *If L2 decomposition succeeds:*  
            *   *For each L2 step:* `L2 Step + L1 Context` → `LLM (L2 step solution)` → `L2 Step result`  
            *   `All L2 Step results + L1 Context` → `LLM (L1 stage synthesis)` → `L1 Stage result`  
    *   `All L1 Stage results + Original query` → `LLM (final synthesis)` → `Final answer`  
    *   The most resource-intensive mode, using multiple LLM calls. Designed for highly complex tasks requiring multi-stage planning and solving. Uses a lower `temperature` for all decomposition and synthesis steps. If L1 decomposition fails, it automatically switches to `Medium` mode. WARNING! This can increase the number of generated tokens by hundreds of times! If you're using a paid API, consider this carefully!  

## 📋 Prerequisites  

*   **Python 3.11+**  
*   **pip** (Python package manager)  
*   **A working LLM server:** You need an accessible HTTP server with an LLM that provides an API compatible with [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create).  
    *   Examples of such servers:  
        *   [Ollama](https://ollama.ai/) (with the `--api` flag or via a separate proxy for OpenAI compatibility)  
        *   [LM Studio](https://lmstudio.ai/) (provides an OpenAI-compatible endpoint)  
        *   [vLLM](https://github.com/vllm-project/vllm) (with an OpenAI-compatible server)  
        *   [OpenRouter](https://openrouter.ai/).  
    *   **Important:** The server must accept POST requests at the path specified in `LLM_API_ENDPOINT` (default: `/v1/chat/completions`) and process JSON data in OpenAI format (fields: `model`, `messages`, `temperature`, `top_p`, `top_k`). The response must also follow the OpenAI format (expected field: `choices[0].message.content`).  

## 🚀 Installation  

1.  **Clone the repository:**  
    ```bash  
    git clone https://github.com/AlexBefest/highCompute.py.git
    cd highCompute.py  
    ```  

2.  **Create and activate a virtual environment (recommended):**  
    *   On Linux/macOS:  
        ```bash  
        python3 -m venv venv  
        source venv/bin/activate  
        ```  
    *   On Windows:  
        ```bash  
        python -m venv venv  
        .\venv\Scripts\activate  
        ```  

3.  **Install dependencies:**  
    Install Python dependencies:  
    ```bash  
    pip install -r requirements.txt  
    ```  

## ⚙️ Configuration  

1.  **Create a `.env` file** in the project root folder.  
2.  **Add `LLM_API_ENDPOINT`, `LLM_MODEL`, and `LLM_API_KEY` to `.env`**, specifying the full URL of your local LLM API endpoint compatible with OpenAI Chat Completions API, your LLM model name, and API key.  

    **Example `.env` file content:**  
    ```dotenv  
    LLM_API_ENDPOINT=http://192.168.2.33:8000/v1/chat/completions  
    LLM_API_KEY="token-abc123"  
    LLM_MODEL="AlexBefest/Gemma3-27B"  
    ```  
    *   Ensure your LLM server is actually listening at this address and path.  

## ▶️ Running the Application  

1.  **Ensure your local LLM server is running** and accessible at the URL specified in `.env` (or the default address).  
2.  **Run the Python script:**  
    ```bash  
    python highCompute.py  
    ```  
3.  **Open the web interface:** The console will display a Gradio message with the local URL, typically `http://127.0.0.1:7860`. Open this URL in your web browser.  

## 💬 Using the Interface  

1.  **Select Computation Level:** Low, Medium, or High, depending on query complexity.  
2.  **(Optional) Adjust parameters:** Modify the `Temperature`, `Top-P`, and `Top-K` sliders if you want to change the LLM's response style.  
    *   `Temperature`: Controls randomness. Lower values (closer to 0) make responses more deterministic and focused. Higher values (closer to 2.0) make responses more creative and diverse but may lead to "hallucinations."  
    *   `Top-P`: Nucleus sampling. The model only considers tokens whose cumulative probability is ≥ `top_p`. A value of `1.0` disables this parameter.  
    *   `Top-K`: Only the top `k` most probable tokens are considered. A value of `0` disables this parameter.  
3.  **Enter your query:** Type your message in the "Your message" text field at the bottom.  
4.  **Submit the query:** Press Enter or click the "Submit" button.  
5.  **View the response:** The LLM's answer will appear in the chat window.  
6.  **Continue the conversation:** Enter follow-up messages. Chat history is preserved and passed to the LLM for context.  
7.  **Clear chat:** Click the "Clear Chat" button to reset history and start a new conversation.  

## ⚠️ Important Notes & Troubleshooting  

*   **LLM API Compatibility:** Ensure your LLM endpoint *strictly* follows the OpenAI Chat Completions API format for requests and responses. Incompatibility will cause errors.  
*   **Performance:** `Medium` and especially `High` modes perform multiple sequential LLM calls, significantly increasing response time compared to `Low` mode.  
*   **Decomposition Quality:** The success of `Medium` and `High` modes heavily depends on the LLM's ability to understand and execute decomposition and synthesis instructions. Quality may vary based on the LLM model and task complexity. Sometimes, the LLM may fail to decompose the task or return a response not in a numbered list format.  
*   **Method Efficiency:** Note that this method may be inefficient with smaller models.  
*   **Network Errors:** If you see "Network error," check if your LLM server is running and accessible at the `.env`-specified address. Verify network and firewall settings.  
*   **JSON Errors:** If you see "Error: Failed to decode JSON response" or "Invalid format," this means the LLM server returned a response that is not valid JSON or does not match the expected OpenAI structure. Check your LLM server logs.

***

# highCompute.py

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Всего один python-файл, подключение через OpenAI Chat Completions API, и вы получаете что-то вроде OpenAI High Compute at home. Совместимы **любые** модели. Используя метод динамического программирования, увеличение количества вычислений в десятки и сотни раз для reasoning и no-reasoning моделей, что значительно повышает качество ответов и способность решать чрезвычайно сложные для LLM задачи. 

Это простое веб-приложение на базе Gradio, предоставляющее интерфейс для взаимодействия с локально запущенной Большой Языковой Моделью (LLM). Ключевой особенностью является возможность выбора "Уровня Вычислений" (Computation Level), который определяет стратегию обработки запроса пользователя: от прямого ответа до многоуровневой декомпозиции задачи для получения более структурированных и полных ответов на сложные запросы.

![image](https://github.com/user-attachments/assets/8886405d-9a49-41ca-89d1-900fdc136d8d)


Приложение подключается к указанному вами API-эндпоинту LLM, совместимому с форматом OpenAI Chat Completions API.

## 🌟 Ключевые возможности

*   **Подключение к локальной LLM:** Работает с вашим собственным LLM-сервером (например, llama.cpp, Ollama, LM Studio, vLLM с OpenAI-совместимым эндпоинтом).
*   **Уровни Вычислений:**
    *   **Low (Низкий):** Прямой запрос к LLM для быстрого ответа. Генерируется N-токенов
    *   **Medium (Средний):** Одноуровневая декомпозиция задачи на подзадачи, их решение и последующий синтез ответа. Подходит для умеренно сложных запросов. Количество генерируемых токенов возводится примерно в квадрат по отношению к low compute. Генерируется N^2 токенов.
    *   **High (Высокий):** Двухуровневая декомпозиция задачи (этапы -> шаги), решение шагов, синтез результатов этапов и финальный синтез общего ответа. Предназначен для наиболее сложных и многокомпонентных задач. Количество генерируемых токенов возводится примерно в куб по отношению к low compute. Генерируется N^3 токенов

## ⚙️ Как это работает: Уровни Вычислений

Основная идея заключается в том, что для сложных задач простой прямой запрос к LLM может не дать оптимального результата. Декомпозиция позволяет разбить сложную проблему на более мелкие, управляемые части, решить их по отдельности, а затем объединить результаты.

1.  **Low (Низкий):**
    *   `Пользовательский запрос` -> `LLM (один вызов)` -> `Ответ`
    *   Самый быстрый режим, подходит для простых вопросов или когда требуется максимально быстрая реакция. Фактически, это стандартный режим чата.

2.  **Medium (Средний):**
    *   `Пользовательский запрос` -> `LLM (запрос на декомпозицию)` -> `Список подзадач`
    *   *Для каждой подзадачи:* `Подзадача + Контекст` -> `LLM (решение подзадачи)` -> `Результат подзадачи`
    *   `Все результаты подзадач + Исходный запрос` -> `LLM (синтез финального ответа)` -> `Финальный ответ`
    *   Использует несколько вызовов LLM. Запросы на декомпозицию и синтез используют пониженную `temperature` для большей предсказуемости.

3.  **High (Высокий):**
    *   `Пользовательский запрос` -> `LLM (декомпозиция Уровня 1)` -> `Список этапов (L1)`
    *   *Для каждого этапа L1:*
        *   `Этап L1 + Контекст` -> `LLM (декомпозиция Уровня 2)` -> `Список шагов (L2)`
        *   *Если декомпозиция L2 не требуется:* `Этап L1 + Контекст` -> `LLM (прямое решение этапа L1)` -> `Результат этапа L1`
        *   *Если декомпозиция L2 удалась:*
            *   *Для каждого шага L2:* `Шаг L2 + Контекст L1` -> `LLM (решение шага L2)` -> `Результат шага L2`
            *   `Все результаты шагов L2 + Контекст L1` -> `LLM (синтез результата этапа L1)` -> `Результат этапа L1`
    *   `Все результаты этапов L1 + Исходный запрос` -> `LLM (финальный синтез)` -> `Финальный ответ`
    *   Самый ресурсоемкий режим, использующий множество вызовов LLM. Предназначен для очень сложных задач, требующих многоэтапного планирования и решения. Использует пониженную `temperature` для всех шагов декомпозиции и синтеза. Если декомпозиция L1 не удается, автоматически переключается на режим `Medium`. ВНИМАНИЕ! Может увеличить количество генерируемых токенов в сотни раз! Если вы используете платный API, вам стоит это учитывать!

## 📋 Предварительные требования

*   **Python 3.11+**
*   **pip** (менеджер пакетов Python)
*   **Работающий LLM сервер:** Вам необходим доступный по HTTP сервер с LLM, который предоставляет API, совместимое с [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create).
    *   Примеры таких серверов:
        *   [Ollama](https://ollama.ai/) (с флагом `--api` или через отдельный прокси для OpenAI совместимости)
        *   [LM Studio](https://lmstudio.ai/) (предоставляет OpenAI-совместимый эндпоинт)
        *   [vLLM](https://github.com/vllm-project/vllm) (с OpenAI-совместимым сервером)
        *   [OpenRouter](https://openrouter.ai/).
    *   **Важно:** Сервер должен принимать POST-запросы на путь, указанный в `LLM_API_ENDPOINT` (по умолчанию `/v1/chat/completions`), и обрабатывать JSON-данные в формате OpenAI (поля `model`, `messages`, `temperature`, `top_p`, `top_k`). Ответ также должен соответствовать формату OpenAI (ожидается поле `choices[0].message.content`).

## 🚀 Установка

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/AlexBefest/highCompute.py.git
    cd highCompute.py
    ```

2.  **Создайте и активируйте виртуальное окружение (рекомендуется):**
    *   На Linux/macOS:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   На Windows:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Установите зависимости:**
    Выполните установку python-зависимостей:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Конфигурация

1.  **Создайте файл `.env`** в корневой папке проекта.
2.  **Добавьте в `.env` переменную `LLM_API_ENDPOINT`, `LLM_MODEL` и `LLM_API_KEY`**, указав полный URL вашего локального LLM API эндпоинта, который совместим с OpenAI Chat Completions API. А также имя вашей LLM-модели и API-ключ.

    **Пример содержимого файла `.env`:**
    ```dotenv
    LLM_API_ENDPOINT=http://192.168.2.33:8000/v1/chat/completions
    LLM_API_KEY="token-abc123"
    LLM_MODEL ="AlexBefest/Gemma3-27B"
    ```
    *   Убедитесь, что ваш LLM сервер действительно слушает этот адрес и путь.

## ▶️ Запуск приложения

1.  **Убедитесь, что ваш локальный LLM сервер запущен** и доступен по URL, указанному в файле `.env` (или по адресу по умолчанию).
2.  **Запустите Python скрипт:**
    ```bash
    python highCompute.py
    ```
3.  **Откройте веб-интерфейс:** В консоли вы увидите сообщение от Gradio с локальным URL, обычно `http://127.0.0.1:7860`. Откройте этот URL в вашем веб-браузере.

## 💬 Использование интерфейса

1.  **Выберите Уровень Вычислений (Computation Level):** Low, Medium или High, в зависимости от сложности вашего запроса.
2.  **(Опционально) Настройте параметры:** Отрегулируйте ползунки `Temperature`, `Top-P`, `Top-K`, если хотите изменить стиль генерации ответа LLM.
    *   `Temperature`: Контролирует случайность. Низкие значения (ближе к 0) делают ответы более детерминированными и сфокусированными. Высокие значения (ближе к 2.0) делают ответы более креативными и разнообразными, но могут привести к "галлюцинациям".
    *   `Top-P`: Нуклеусное сэмплирование. Модель рассматривает только токены, чья суммарная вероятность больше или равна `top_p`. Значение `1.0` отключает этот параметр.
    *   `Top-K`: Рассматриваются только `k` наиболее вероятных токенов. Значение `0` отключает этот параметр.
3.  **Введите ваш запрос:** Напишите сообщение в текстовое поле "Your message" внизу.
4.  **Отправьте запрос:** Нажмите Enter или кнопку "Submit".
5.  **Просмотрите ответ:** Ответ LLM появится в окне чата.
6.  **Продолжайте диалог:** Вводите следующие сообщения. История чата будет сохраняться и передаваться LLM для контекста.
7.  **Очистить чат:** Нажмите кнопку "Clear Chat", чтобы сбросить историю и начать новый диалог.

## ⚠️ Важные замечания и устранение неисправностей

*   **Совместимость LLM API:** Убедитесь, что ваш LLM эндпоинт *строго* следует формату OpenAI Chat Completions API для запросов и ответов. Несовместимость формата приведет к ошибкам.
*   **Производительность:** Режимы `Medium` и особенно `High` выполняют несколько последовательных вызовов LLM, что значительно увеличивает время ожидания ответа по сравнению с режимом `Low`.
*   **Качество декомпозиции:** Успех режимов `Medium` и `High` сильно зависит от способности LLM понимать и выполнять инструкции по декомпозиции и синтезу. Качество может варьироваться в зависимости от используемой модели LLM и сложности исходной задачи. Иногда LLM может не суметь разбить задачу или вернуть ответ не в виде нумерованного списка.
*   **Эффективность метода:** Нужно понимать, что данный метод может быть неэффективен с небольшими моделями
*   **Сетевые ошибки:** Если вы видите "Network error", проверьте, запущен ли ваш LLM сервер и доступен ли он по указанному в `.env` адресу. Проверьте настройки сети и файрвола.
*   **Ошибки JSON:** Если вы видите "Error: Failed to decode JSON response" или "Invalid format", это означает, что LLM сервер вернул ответ, который не является валидным JSON или не соответствует ожидаемой структуре OpenAI. Проверьте логи вашего LLM сервера.
