# ASReview LAB local em Docker para o fluxo de triagem (corpus -> ASReview -> decisoes).
# Imagem oficial: https://asreview.readthedocs.io/en/latest/lab/installation.html
#
# Uso:
#   .\scripts\asreview_docker.ps1 -Action up      # cria (na primeira vez baixa a imagem) e inicia
#   .\scripts\asreview_docker.ps1 -Action down    # para o container (projetos sao mantidos no volume)
#   .\scripts\asreview_docker.ps1 -Action status  # lista o container
#   .\scripts\asreview_docker.ps1 -Action logs    # ultimas 50 linhas de log
#   .\scripts\asreview_docker.ps1 -Action remove  # remove o container (o volume de projetos permanece)
#
# Depois de "up", abra http://localhost:5000 no navegador e importe
# exports/asreview/openalex_asreview.csv (botao "Gerar CSV do corpus para o ASReview"
# da pagina Triagem ASReview) como dataset de um novo projeto.
param(
  [ValidateSet("up", "down", "status", "logs", "remove")][string]$Action = "up",
  [int]$Port = 5000,
  [string]$Name = "asreview-lab",
  [string]$Image = "ghcr.io/asreview/asreview:latest",
  [string]$Volume = "ale-biblioteca-asreview"
)
$ErrorActionPreference = "Stop"

function Test-ContainerExists {
  docker inspect $Name 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}

switch ($Action) {
  "up" {
    docker --version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "Docker nao encontrado ou o daemon nao esta ativo. Instale o Docker Desktop e inicie-o."
    }
    if (-not (Test-ContainerExists)) {
      Write-Host "Criando container '$Name' a partir da imagem oficial ($Image)..."
      Write-Host "Na primeira execucao a imagem e baixada; isso pode levar alguns minutos."
      docker create --name $Name -p "${Port}:${Port}" -v "${Volume}:/project_folder" $Image lab --port $Port | Out-Null
      if ($LASTEXITCODE -ne 0) {
        throw "Falha ao criar o container (verifique o Docker Desktop e a conexao)."
      }
    }
    docker start $Name | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "Falha ao iniciar o container; execute: .\scripts\asreview_docker.ps1 -Action logs"
    }
    Write-Host ""
    Write-Host "ASReview LAB em http://localhost:${Port}"
    Write-Host "Projetos persistem no volume Docker '${Volume}'."
  }
  "down" {
    docker stop $Name 2>$null | Out-Null
    Write-Host "Container parado; os projetos permanecem no volume '${Volume}'."
  }
  "status" {
    docker ps -a --filter "name=$Name" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
  }
  "logs" {
    docker logs --tail 50 $Name
  }
  "remove" {
    docker stop $Name 2>$null | Out-Null
    docker rm $Name 2>$null | Out-Null
    Write-Host "Container removido. Os projetos continuam no volume '${Volume}' (remova com: docker volume rm ${Volume})."
  }
}
