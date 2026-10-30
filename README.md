# Sulamita Bistrô — Linha Fit

Quiz mobile-first para o evento de lançamento da Linha Fit, com resultado “Qual SulaLover é você?”, cadastro obrigatório para participação nos sorteios, área administrativa protegida, relatório Excel e cópia opcional para Google Sheets.

## Executar localmente

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
flask --app app run
```

Sem `DATABASE_URL`, o desenvolvimento local usa SQLite em `instance/sulamita.db`. Não use SQLite como banco de produção em uma hospedagem com disco efêmero.

## Fluxo e dados

1. Antes do quiz, a pessoa informa primeiro nome, WhatsApp com DDD e bairro/cidade, e aceita o aviso de privacidade.
2. A participação nos sorteios exige responder às cinco perguntas e concluir o envio. A autorização para receber ofertas pelo WhatsApp é separada, opcional e começa desmarcada.
3. Após a última pergunta, o cadastro, as cinco respostas e o perfil são enviados juntos e salvos no banco. O banco mantém uma ficha única por WhatsApp normalizado e cada novo envio gera um registro histórico separado de respostas e autorização.
4. Uma chave de envio idempotente permite tentar novamente após falhas de conexão sem criar um segundo registro para a mesma tentativa.

O banco armazena respostas com IDs e textos apresentados, pontuação dos cinco perfis, preferências declaradas separadamente do resultado, origem e versão da campanha, data/hora e versões dos avisos. O formulário não pergunta sobre dados de saúde nem infere preferência por doces a partir do perfil; somente a resposta explícita sobre produto é considerada interesse em doces.

## Banco e publicação

O Neon é o banco principal e o Render hospeda o aplicativo. Configure a connection string PostgreSQL do Neon em `DATABASE_URL` como variável privada no Render. O SQLite local não deve ser usado em produção.

Ao iniciar, o aplicativo cria as tabelas novas e executa uma migração aditiva das inscrições existentes, preservando respostas e autorizações já registradas. Inscrições antigas são associadas a um contato normalizado quando o telefone é válido; os dados originais permanecem na tabela de histórico. Não execute mudanças de banco manualmente para esta versão.

## Painel e exportação

O painel `/admin` exige autenticação HTTP Basic usando `ADMIN_USER` e `ADMIN_PASSWORD`. Ele mostra até 200 contatos únicos, o resultado e as preferências mais recentes, além do histórico de respostas e autorizações. O botão de exportação baixa um arquivo Excel com abas separadas para contatos únicos, cada participação/respostas e resumo do evento. Guarde o arquivo em local privado, pois contém dados pessoais.

## Google Sheets opcional

A inscrição é salva primeiro no Neon. Se configurado, o app copia o histórico para uma planilha privada usando linhas estáveis por ID; falhas de cópia não impedem o cadastro. Defina `SHEETS_SERVICE_ACCOUNT_JSON` e `SHEETS_SPREADSHEET_ID` no Render para ativar a integração.

Esta versão usa 22 colunas no cabeçalho da aba `Respostas`. Se a planilha já tiver um cabeçalho da versão anterior, faça uma cópia privada de segurança e atualize a primeira linha para corresponder aos novos cabeçalhos antes de ativar a sincronização. Sem as variáveis do Sheets, as respostas continuam no Neon.

## Privacidade e identidade visual

O caminho `/privacidade` mostra um aviso inicial baseado no fluxo e nos dados coletados. Antes de publicar esta versão e divulgar o QR Code, a Sulamita deve validar o texto, completar a identificação legal da empresa, confirmar prazos de retenção e publicar as regras oficiais do sorteio.

A interface usa Montserrat e declara Lovelo como fonte de títulos. O arquivo oficial da fonte Lovelo ainda precisa ser fornecido para que ela apareça em dispositivos sem essa fonte instalada. As ilustrações fornecidas foram copiadas para `static/img/` e associadas aos perfis.
