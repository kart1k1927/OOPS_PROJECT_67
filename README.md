<a id="readme-top"></a>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      </li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Committing Changes</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

OOPS PROJECT

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple example steps.


### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/gitblip/Analog-Neural_Network_simulation.git
   ```

    ![pic to help](assets/images/HelpfulPicyes.png)

2. Enter the repo and change your branch to avoid pushing to main
    ```sh
    cd Analog-Neural_Network_simulation
    git switch -c <branch-name>
    ```
3. Make sure to check which branch youre pushing your update to
   ```sh
   git remote -v # confirm the changes
   ```
4. Create a virtual env (venv) and reload bash thorugh source cmd or jstu run this below cmd after switch branches
   ```** pwsh**
   python3 -m venv .venv && source .venv\Scripts\activate && pip install -r requirements.txt
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE -->
## Committing changes

After createing a seperate and new branch, push updates to here

1. Create the .git folder (it should already have been created after cloning the repo)
    ```sh
    git init
    ```
2. After adding your changes, you need to add those changes that you want to ur init file before pushing to your branch
    ```sh
    git add .
    #this is a comment, not always ull need to add everything, sometimes u want add only seom things, figure it out if u to remove stuff from your commit or whatev is required, but beware of commit history and adding to commit before pushing the previous commit
    ```
3. Commit your changes
    ```sh
    git commit -m "whatev msg u want to display with your commit"
    git status
    #git status helps you see what files will be pushed
    ```
4. Check your branch and then push, DONT PUSH TO MAIN  
    ```sh
    git branch --show-current
    #for the first time youll need to run this
    git push -u origin <branch name>
    # '-u' sets your upstream sot hat next time onwards you can just type the following
    git push
    ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- Must Create endpoints
- Must create the webpages
- Authentication

<p align="right">(<a href="#readme-top">back to top</a>)</p>

