# Plano: Testar e Limpar lista5.m3u

## Análise do Arquivo
- **Total de linhas**: 83 (1 cabeçalho + 82 de canais)
- **Cada canal**: 2 linhas (#EXTINF + URL)

## Canais Únicos Identificados
| Canal | Linhas |
|-------|--------|
| ABC News - World News Tonight | 2-29 (14 URLs) |
| ABC News Live | 30-45 (8 URLs) |
| Fox News Channel | 46-47 (1 URL) |
| Fox Business Go | 48-49 (1 URL) |
| CBS News 24/7 | 50-83 (17 URLs) |

## Estratégia de Teste
Usar `curl` para verificar se cada URL retorna HTTP 200:
```bash
curl -s -o /dev/null -w "%{http_code}" <URL>
```

## Comandos para Executar
1. Criar script temporário para testar URLs
2. Executar testes em paralelo (máx 10 simultâneos)
3. Gerar nova lista com apenas canais funcionando (HTTP 200)
4. Sobrescrever lista5.m3u

## Resultado Esperado
- Lista limpa com apenas canais que retornam HTTP 200
- Remover canais com erro (4xx, 5xx, timeout)