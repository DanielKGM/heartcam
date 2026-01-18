<a id="topo"></a>

[![DOI][doi-shield]][doi-url]
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Unlicense License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/DanielKGM/heartcam">
    <img src="assets/logo.png" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">HeartCam: Batimentos Cardíacos <i>Online</i></h3>

  <p align="center">
    HeartCam é uma aplicação <i>web/<strong>online</strong></i> que realiza fotopletismografia remota (rPPG) através de celulares e computadores. Os <strong>batimentos cardíacos</strong> são estimados em tempo real, a partir do processamento de imagens da <strong>câmera</strong>.
    <br />
    <br />
    <a href="https://heartcam.koyeb.app/"><strong>ACESSAR <i>WEBSITE</i> »</strong></a>
    <br />
    <br />
    <a href="https://github.com/github_username/repo_name/issues/new?labels=bug&template=bug-report---.md">Reportar Erro</a>
    &middot;
    <a href="https://github.com/github_username/repo_name/issues/new?labels=enhancement&template=feature-request---.md">Sugerir Algo</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary><b>Clique Aqui</b> para Exibir o Sumário</summary>
  <ol>
    <li>
      <a href="#sobre-o-projeto">Sobre o Projeto</a>
      <ul>
        <li><a href="#tecnologias">Tecnologias</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



## Sobre o Projeto

[![Screenshot Produto][screenshot-produto]](https://heartcam.koyeb.app/)

<div align="justify">
O <b>HeartCam</b> é um sistema desenvolvido para monitoramento não invasivo de sinais vitais. Utilizando a técnica de <i>Eulerian Video Magnification</i> (EVM) e análise espectral (FFT), o sistema consegue detectar as micro-variações de cor na pele causadas pela circulação sanguínea, invisíveis a olho nu.
<br/><br/>
Este projeto foi desenvolvido para a disciplina Processamento de Imagens 2025.2 da Universidade Federal do Maranhão (UFMA) e seu algorítmo de magnificação de vídeo baseia-se em:
</div><br/>

> WU, Hao-Yu et al. <b>Eulerian Video Magnification for Revealing Subtle Changes in the World</b>. ACM Transactions on Graphics (Proc. SIGGRAPH 2012), v. 31, n. 4, 2012. Disponível em: <<a href="https://people.csail.mit.edu/mrub/evm/">https://people.csail.mit.edu/mrub/evm/</a>>.

<p align="right">(<a href="#topo">voltar ao topo</a>)</p>

### Tecnologias

|  | Aplicação |
|---------|---------------|
| [![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=fff)](#) | Linguagem principal do <i>backend</i> e processamento de dados. |
| [![Flask](https://img.shields.io/badge/Flask-000?style=for-the-badge&logo=flask&logoColor=fff)](#) | <i>Framework web</i> para gerenciamento de rotas e servidor. |
| [![NumPy](https://img.shields.io/badge/NumPy-4DABCF?style=for-the-badge&logo=numpy&logoColor=fff)](#) | Cálculos matemáticos, manipulação de arrays e FFT. |
| [![OpenCV](https://img.shields.io/badge/OpenCV-27338e?style=for-the-badge&logo=OpenCV&logoColor=white)](#) | Visão computacional, detecção facial (Haar Cascades) e construção de pirâmides gaussianas para o algoritmo EVM. |
| [![SocketIO](https://img.shields.io/badge/Socket.io-010101?style=for-the-badge&logo=Socket.io&logoColor=white)](#) | Comunicação bidirecional em tempo real entre cliente e servidor. |
| [![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=fff)](#) | Estilização da interface e componentes responsivos. |
| [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=000)](#) [![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=fff)](#) | Lógica do cliente e gráficos dinâmicos. |
| [![HTML](https://img.shields.io/badge/HTML-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white)](#) | Estrutura semântica das páginas web. |
| [![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=fff)](#) | Containerização da aplicação para fácil distribuição e <i>deploy</i>. |

<p align="right">(<a href="#topo">voltar ao topo</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.
* npm
  ```sh
  npm install npm@latest -g
  ```

### Installation

1. Get a free API Key at [https://example.com](https://example.com)
2. Clone the repo
   ```sh
   git clone https://github.com/github_username/repo_name.git
   ```
3. Install NPM packages
   ```sh
   npm install
   ```
4. Enter your API in `config.js`
   ```js
   const API_KEY = 'ENTER YOUR API';
   ```
5. Change git remote url to avoid accidental pushes to base project
   ```sh
   git remote set-url origin github_username/repo_name
   git remote -v # confirm the changes
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Use this space to show useful examples of how a project can be used. Additional screenshots, code examples and demos work well in this space. You may also link to more resources.

_For more examples, please refer to the [Documentation](https://example.com)_

<p align="right">(<a href="#readme-top">back to top</a>)</p>




<!-- ROADMAP -->
## Roadmap

- [ ] Feature 1
- [ ] Feature 2
- [ ] Feature 3
    - [ ] Nested Feature

See the [open issues](https://github.com/github_username/repo_name/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>




<!-- CONTACT -->
## Contact

Your Name - [@twitter_handle](https://twitter.com/twitter_handle) - email@email_client.com

Project Link: [https://github.com/github_username/repo_name](https://github.com/github_username/repo_name)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* []()
* []()
* []()

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[doi-shield]: https://img.shields.io/badge/DOI-18282893-black?style=for-the-badge
[doi-url]: https://doi.org/10.5281/zenodo.18282892
[contributors-shield]: https://img.shields.io/github/contributors/DanielKGM/heartcam.svg?style=for-the-badge
[contributors-url]: https://github.com/DanielKGM/heartcam/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/DanielKGM/heartcam.svg?style=for-the-badge
[forks-url]: https://github.com/DanielKGM/heartcam/network/members
[stars-shield]: https://img.shields.io/github/stars/DanielKGM/heartcam.svg?style=for-the-badge
[stars-url]: https://github.com/DanielKGM/heartcam/stargazers
[issues-shield]: https://img.shields.io/github/issues/DanielKGM/heartcam.svg?style=for-the-badge
[issues-url]: https://github.com/DanielKGM/heartcam/issues
[license-shield]: https://img.shields.io/github/license/DanielKGM/heartcam.svg?style=for-the-badge
[license-url]: https://github.com/DanielKGM/heartcam/blob/main/LICENSE.md
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/daniel-campos-galdez-monteiro/
[screenshot-produto]: https://placehold.co/600x400?text=Screenshots+do+HeartCam
