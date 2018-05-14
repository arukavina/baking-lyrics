import React from "react";
import { Button, Grid, Row, Col } from "react-bootstrap";

var $ = require('jquery');

export default class Hello extends React.Component {
    constructor(props) {
        super(props);
        this.state = {greeting: 'Random Lyrics ' + this.props.name};

        // This binding is necessary to make `this` work in the callback
        this.getPythonHello = this.getPythonHello.bind(this);
    }

    personaliseGreeting(greeting) {
        this.setState({greeting: greeting + ' ' + this.props.name + '!'});
    }

    getPythonHello() {
        $.get(window.location.href + 'hello', (data) => {
            console.log(data);
            this.personaliseGreeting(data);
        });
    }

    render () {
        return (
                <div>
                    <h1>{this.state.greeting}</h1>
                    <div class="wrapper">
                      <div class="item1">
                        <Button bsSize="large" bsStyle="danger" onClick={this.getPythonHello}>
                        Get some Lyrics
                        </Button>
                      </div>
                    </div>
                </div>
        );
    }
}