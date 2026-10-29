# Sulamita Bistrô — lançamento Linha Fit

Aplicação independente de captação de participantes para o lançamento da Linha Fit. A experiência combina um quiz curto de preferências com cadastro, resultado personalizado e exportação protegida dos leads em CSV.

## Executar localmente

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite o `.env` com os dados do banco e uma senha administrativa. Para desenvolvimento, é possível remover `DATABASE_URL`; a aplicação então cria `instance/sulamita.db`. Não use o SQLite local como banco de produção em hospedagens com disco efêmero.

```powershell
flask --app app run
```

Abra `http://127.0.0.1:5000`. O painel e o CSV ficam em `/admin` e exigem autenticação HTTP Basic com `ADMIN_USER` e `ADMIN_PASSWORD`.

## Banco persistente e publicação

O app aceita PostgreSQL por `DATABASE_URL` e usa `pool_pre_ping` para renovar conexões após períodos ociosos. O Neon é o banco principal; suspender o compute não remove os registros.

1. Crie um banco PostgreSQL no Neon e copie a connection string com SSL.
2. Publique este diretório no Render usando o `render.yaml`; configure `DATABASE_URL`, `ADMIN_USER`, `ADMIN_PASSWORD`, `SHEETS_SERVICE_ACCOUNT_JSON` e `SHEETS_SPREADSHEET_ID` como variáveis privadas. O blueprint gera `SECRET_KEY`.
3. O blueprint instala os requisitos e inicia o app com `gunicorn app:app`.
4. Abra `/admin` e teste o download do CSV e a sincronização com a planilha antes do evento.

As tabelas são criadas na inicialização sem apagar dados existentes; inscrições antigas sem tarefa de cópia são adicionadas à fila automaticamente.

## Cópia automática para Google Sheets

A inscrição e sua tarefa persistente de sincronização são gravadas primeiro no Neon; o resultado do quiz pode ser exibido sem aguardar o Google Sheets. Em seguida, um worker tenta escrever a resposta em uma linha fixa da planilha, identificada pelo ID da inscrição; novas tentativas atualizam a mesma linha em vez de duplicá-la. Se o Sheets estiver fora do ar ou o Render reiniciar antes de terminar, a resposta permanece no banco e a tarefa fica pendente. O app tenta sincronizar após novas inscrições e quando alguém autorizado abre `/admin`; erros e pendências aparecem nesse painel. As chamadas ao Google têm timeout e usam valores brutos para que texto fornecido por participantes não seja interpretado como fórmula.

1. Crie uma planilha privada chamada, por exemplo, `Sulamita — Linha Fit`, com uma aba chamada `Respostas`. Deixe a primeira linha vazia; o app cria os cabeçalhos.
2. No Google Cloud, habilite Google Sheets API, crie uma service account e gere sua chave JSON.
3. Compartilhe a planilha com o `client_email` da service account como **Editor**. Não habilite o compartilhamento público.
4. Em Render, configure `SHEETS_SERVICE_ACCOUNT_JSON` com o conteúdo integral do JSON e `SHEETS_SPREADSHEET_ID` com o trecho entre `/d/` e `/edit` na URL da planilha. Trate o JSON como uma senha: mantenha-o apenas nas variáveis privadas do Render, nunca no Git ou no front-end.
5. Publique/reinicie o serviço e envie um cadastro de teste. Confirme a linha na planilha, depois abra `/admin` para verificar o estado e exporte o CSV.

A planilha é uma cópia operacional, não substitui o Neon nem backups independentes. Mantenha o CSV exportado em local privado e restrinja o acesso às respostas, que contêm dados pessoais. Sem as variáveis do Sheets configuradas, o app ainda salva as inscrições no Neon e avisa no painel que o espelhamento não foi ativado.

## Privacidade

O cadastro pede nome, WhatsApp e, opcionalmente, e-mail. O consentimento para registrar a participação é obrigatório; o aceite de comunicações promocionais é separado e opcional. A planilha contém dados pessoais e deve ser acessada e compartilhada somente por pessoas autorizadas. Adapte o aviso de privacidade ao controlador e aos canais usados pela Sulamita antes da publicação.

## Identidade visual

O quiz foi alinhado ao perfil público da Sulamita: marrom queimado, tons de massa e creme, amarelo vivo da Linha Fit, selo com o nome em duas linhas e a assinatura “É mais que empada, é Sulamita”. O destaque de 31/10 em São Francisco também aparece no início. A marca do cabeçalho é uma aproximação tipográfica; substitua pelo arquivo oficial do logo quando ele estiver disponível. As perguntas e perfis ficam em `quiz.py`.
