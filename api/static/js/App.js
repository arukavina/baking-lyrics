
import React from "react";
import Hello from "./Hello";
import { PageHeader } from "react-bootstrap";

require('../css/bl.css');
var $ = require('jquery');

import logo from '../images/logo.png';
const Logo = () => (
  <div className="logo">
    <img src={`dist/${logo}`}/>
  </div>);

const Footer = () => (
  <div>
    <span className='credit'>
      Copyright © 2018 Baking Lyrics | Contact: <a href='rukavina.andrei@gmail.com' type='email'>rukavina.andrei@gmail.com</a>
    </span>
    <span className='p5'>
      Made with <i className="fa fa-heart pulse"></i>
      by
      <a href="https://plataforma5.la" target="_blank" id='plataforma'>
        <strong> Plataforma 5  </strong>
      </a>
    </span>
  </div>
);

export default class App extends React.Component {
    constructor(props) {
        super(props);
    }
    render () {
        return (
          <div>
            <Logo/>
            <div className='header-contents'>
              <Hello/>
            </div>
            <Footer />
          </div>
        );
    }
}
